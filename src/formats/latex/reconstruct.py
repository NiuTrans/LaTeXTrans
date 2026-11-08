from typing import List, Dict, Any
import os
import re
from .utils import *

class LatexConstructor:
    def __init__(self, 
                 sections: List[Dict[str, Any]], 
                 captions: List[Dict[str, Any]], 
                 envs: List[Dict[str, Any]],
                 inputs: List[Dict[str, Any]],
                 newcommands: List[Dict[str, Any]],
                 output_latex_dir: str
                 ):
        self.sections = sections
        self.captions = captions
        self.envs = envs
        self.inputs = inputs
        self.newcommands = newcommands
        self.output_latex_dir = output_latex_dir

    def construct(self):
        """
        construct the translated latex  project  from the sections, envs, captions and inputs
        """
        tex = self._merge_sections()
        tex = self._revert_envs(tex)
        tex = self._revert_captions(tex)
        tex = self._revert_newcommands(tex)

        # process japanese specific packages ----------
        # tex = self._comment_out_latex_packages_for_ja(tex)
        # tex = self._add_lualatex_option_to_documentclass_for_ja(tex)
        # ---------------------------------------------


        self._revert_inputs(tex)
    
    def _merge_sections(self) -> str:
        """
        Merge all the sections to a tex
        """
        tex = ""
        for section in self.sections:
            tex += section["trans_content"] + "\n"
        return tex

    def _revert_envs(self, tex: str) -> str:
        """
        Revert all the envs to tex
        """
        for env in self.envs:
            placeholder = env["placeholder"]
            tex = tex.replace(placeholder, env["trans_content"])

        return tex
             
    def _revert_captions(self, tex: str) -> str:
        """
        Revert all the captions to tex
        """
        for caption in self.captions:
            placeholder = caption["placeholder"]
            translated = caption["trans_content"]
            if caption.get("cap_type") in {"captionof", "captionof*"}:
                pattern = get_captionof_pattern()
                original = pattern.fullmatch(caption["content"].strip())
                result = pattern.fullmatch(translated.strip())
                # The first argument is a LaTeX float type, not translatable prose.
                if (
                    original is None or result is None
                    or result.group("command") != original.group("command")
                    or result.group("type")[1:-1].strip() != original.group("type")[1:-1].strip()
                ):
                    translated = caption["content"]
            tex = tex.replace(placeholder, translated)

        return tex                              
    
    def _revert_newcommands(self, tex: str) -> str:
        """
        Revert all the newcommands to tex
        """
        for newcommand in self.newcommands:
            placeholder = newcommand["placeholder"]
            tex = tex.replace(placeholder, newcommand["content"])

        return tex
                                          
    def _revert_inputs(self, tex: str):
        begin_map = {sec["begin"]: sec for sec in self.inputs}
        end_map = {sec["end"]: sec for sec in self.inputs}
        pattern = re.compile(r"<PLACEHOLDER_[^>]+?_begin>|<PLACEHOLDER_[^>]+?_end>")

        stack = []
        pos = 0  

        while True:
            match = pattern.search(tex, pos)
            if not match:
                break

            tag = match.group()

            if tag in begin_map:
                stack.append((tag, match.start()))
                pos = match.end()  
            elif tag in end_map:
                if not stack:
                    raise ValueError(f"Unmatched end tag: {tag}")
                begin_tag, begin_pos = stack.pop()
                if end_map[tag] != begin_map[begin_tag]:
                    raise ValueError(f"Mismatched tags: {begin_tag} vs {tag}")

                input_info = begin_map[begin_tag]
                end_pos = match.end()

                inner_start = begin_pos + len(begin_tag)
                inner_end = match.start()
                inner_content = tex[inner_start:inner_end].strip()

                relative_path = input_info["path"]
                if not relative_path.endswith(".tex"):
                    relative_path += ".tex"
                output_path = os.path.join(self.output_latex_dir, relative_path)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(inner_content + "\n")

                tex = tex[:begin_pos] + input_info["command"] + tex[end_pos:]

                pos = begin_pos + len(input_info["command"])

            else:
                pos = match.end()

        if stack:
            unclosed_tags = [tag for tag, _ in stack]
            print(f"⚠️ Warning: Unclosed begin placeholder(s) found and skipped: {unclosed_tags}")
        
        residual_matches = re.findall(r"<PLACEHOLDER_[^>]*>", tex)
        if residual_matches:
            print(f"⚠️ Warning: Residual placeholders found and removed: {residual_matches}")
            tex = re.sub(r"<PLACEHOLDER_[^>]*>", "", tex)

        tex = add_ctex_package(tex) # zh
        # tex = add_ja_package(tex)  # ja

        main_file_path = find_main_tex_file(self.output_latex_dir)
        if os.path.exists(main_file_path):
            with open(main_file_path, "w", encoding="utf-8") as f:
                f.write(tex)
        else:
            print(f"⚠️ Warning: No main.tex file found in {self.output_latex_dir}, creating a new one.")
            main_file_path = os.path.join(self.output_latex_dir, "main.tex")
            with open(main_file_path, "w", encoding="utf-8") as f:
                f.write(tex)

    def _comment_out_latex_packages_for_ja(self, tex):

        packages_to_comment = [
            r'\usepackage[utf8]{inputenc}',
            r'\usepackage[T1]{fontenc}',
            r'\usepackage{times}',
            r'\usepackage{mathptmx}',
            r'\pdfoutput=1'
        ]
        
        lines = tex.splitlines()
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            for package in packages_to_comment:
                if stripped_line.startswith(package) and not stripped_line.startswith('%'):
                    lines[i] = line.replace(package, f'% {package}')
                    break 
        
        return '\n'.join(lines)        

    def _add_lualatex_option_to_documentclass_for_ja(self, tex):

        import re
        
        pattern = re.compile(r'\\documentclass(?:\[([^\]]*)\])?(\{.*?\})')
        
        def replacer(match):
            options = match.group(1)
            class_name = match.group(2)
            
            if options:
                if 'lualatex' not in options:
                    new_options = options + ', lualatex'
                else:
                    new_options = options
                return f'\\documentclass[{new_options}]{class_name}'
            else:
                return f'\\documentclass[lualatex]{class_name}'
        
        modified_source = pattern.sub(replacer, tex)
        
        return modified_source
    


# caption_dir = "D:\code\AutoLaTexTrans\output\ch_arXiv-2504.10471v1\captions_map.json"
# section_dir = "D:\code\AutoLaTexTrans\output\ch_arXiv-2504.10471v1\sections_map.json"
# input_dir = "D:\code\AutoLaTexTrans\output\ch_arXiv-2504.10471v1\inputs_map.json"
# envs_dir = "D:\code\AutoLaTexTrans\output\ch_arXiv-2504.10471v1\envs_map.json"
# sections = read_json_file(section_dir)
# captions= read_json_file(caption_dir)
# inputs = read_json_file(input_dir)
# envs = read_json_file(envs_dir)
# dir = "D:\code\AutoLaTexTrans/tests/10471"


# latexconstructor = LatexConstructor(
#     sections=sections,
#     captions=captions,
#     envs=envs,
#     inputs=inputs,
#     output_latex_dir=dir
# )
# latexconstructor.construct()
