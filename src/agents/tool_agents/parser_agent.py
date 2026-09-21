from typing import Dict, Any
from src.agents.tool_agents.base_tool_agent import BaseToolAgent
import src.formats.latex.prompts as pm
from pathlib import Path
import sys
import os
import requests
import time

base_dir = os.getcwd()
sys.path.append(base_dir)

class ParserAgent(BaseToolAgent):
    def __init__(self, 
                 config: Dict[str, Any], 
                 project_dir: str = None,
                 output_dir: str = None
                 ):
        super().__init__(agent_name="ParserAgent", config=config)
        self.config = config
        self.project_dir = project_dir  # Project path for parsing
        self.output_dir = output_dir  # Output directory for parsed files
        self.model = config["llm_config"].get("model", "gpt-4o")
        self.base_url = config["llm_config"].get("base_url", None)
        self.API_KEY = config["llm_config"].get("api_key", None)
        self.timeout = float(config["llm_config"].get("timeout", 100))

    def execute(self) -> Any:
        pm.init_prompts(self.config["source_language"], self.config["target_language"])
        self.log(f"🤖💬 Starting parsing for project...⏳: {os.path.basename(self.project_dir)}.")

        from src.formats.latex.parser import LatexParser
        latex_parser = LatexParser(self.project_dir, self.output_dir)
        latex_parser.parse() 

        env_need_trans = []
        if latex_parser.envs_json:
            for env in latex_parser.envs_json:
                if env["need_trans"] and env["env_name"] not in ['abstract', 'itemize']:
                    env_need_trans.append(env)

        if env_need_trans:
            self.log(f"🤖💬 Starting seting need_trans for project...⏳: {os.path.basename(self.project_dir)}.")

            placeholder_to_index = {
                        env["placeholder"]: i for i, env in enumerate(latex_parser.envs_json)
                    }
            
            total_envs = len(env_need_trans)
            for idx, env in enumerate(env_need_trans, start=1):
                if idx == 1 or idx == total_envs or idx % 10 == 0:
                    print(f"Setting need_trans: {idx}/{total_envs}")
                i = placeholder_to_index.get(env["placeholder"])
                if i is not None:
                    latex_parser.envs_json[i]["need_trans"] = self._request_llm_for_judge(
                                                                    pm.set_need_trans_for_envs_system_prompt,
                                                                    env["content"]
                                                                    )

        self.save_file(Path(self.output_dir, "inputs_map.json"), "json", latex_parser.inputs_json)
        self.save_file(Path(self.output_dir, "envs_map.json"), "json", latex_parser.envs_json)
        self.save_file(Path(self.output_dir, "captions_map.json"), "json", latex_parser.captions_json)
        self.save_file(Path(self.output_dir, "newcommands_map.json"), "json", latex_parser.newcommands_json)
        self.save_file(Path(self.output_dir, "sections_map.json"), "json", latex_parser.sections_json)

        self.log(f"✅ Successfully parsed {os.path.basename(self.project_dir)}.")
        self.log(f"🤖💬 Parsed files are saved in {self.output_dir}.")
            
    # def _set_need_trans(self, env: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     Determine whether translation is needed for the given environment.
    #     """
    #     # if not env.get("need_trans", False) and env.get("env_name", "") not in ['abstract', 'itemize']:

    #     set_env = env.copy()
    #     set_env["need_trans"] = self._request_llm_for_judge(
    #         set_need_trans_for_envs_system_prompt,
    #         set_env["content"]
    #     )
    #     return set_env

    def _request_llm_for_judge(self, system_prompt: str, text: str) -> bool:
        """
        Request the api to set need trans for env
        """
        payload = {
            "model": f"{self.model}",
            "messages": [
                {
                    "role": "system", 
                    "content": f"{system_prompt}"
                },
                {
                    "role": "user", 
                    "content": f"{text}"
                }
            ],
            "temperature": 0,
            # "max_length": 100000,
            "max_tokens": 50
        }

        headers = {
            "Authorization": f"Bearer {self.API_KEY}",
            "Content-Type": "application/json"
        }
        
        
        for attempt in range(1, 4):
            try:
                response = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()  
                result = response.json()
                output = result["choices"][0]["message"]["content"].strip()

                if output.lower() == "true":
                    return True
                elif output.lower() == "false":
                    return False
                else:
                    return True                
            except requests.exceptions.RequestException as e:
                if attempt < 3:
                    print(f"{e}")
                    time.sleep(3)  
                else:
                    print(f"⚠️ Failed to Set need trans, set True.")
                    return True
                
