from typing import Any, Dict, Optional
from .utils import *
import tiktoken
import sys

from src.utils.progress import st


class LatexParser:
    def __init__(self, dir: str, output_dir: str):
        self.inputs_json = []
        self.envs_json = []
        self.captions_json = []
        self.newcommands_json = []
        self.sections_json = []
        self.dir = dir # LaTex profect directory
        self.output_dir = output_dir # Output directory for parsed files
        self.env_count = 0
        self.caption_count = 0

    def parse(self):
        """
        Parse the LaTeX document and return the parsed content.
        """
        sys.stderr = open(os.devnull, 'w')
        process_b = st.empty()
        with process_b:
            process_bar = st.progress(0, text="Parsing LaTeX document...")
        sys.stderr = sys.__stderr__

        main_tex_file = find_main_tex_file(self.dir) 
        if not main_tex_file:
            print("⚠️ Warning: There is no main tex file to compile in this directory.")
            return None

        sys.stderr = open(os.devnull, 'w')
        process_bar.progress(10, text="Finding main tex file...")
        sys.stderr = sys.__stderr__

        main_tex = read_tex_file(main_tex_file)
        if not main_tex:
            print("⚠️ Warning: The main tex file is empty.")
            return None
        
        sys.stderr = open(os.devnull, 'w')
        process_bar.progress(20,text="Reading main tex file...")
        sys.stderr = sys.__stderr__

        main_tex = remove_comments(main_tex)
        full_tex = self._merge_inputs(main_tex)
        full_tex = self._extract_newcommands(full_tex)

        full_tex = compress_newlines(full_tex) # Delete the redundant blank lines to prevent the large model from missing placeholders during translation

        self._split_to_sections(full_tex)

        self._merge_short_sections(min_tokens=50)  # Merge short sections to avoid too many sections

        total_sections = len(self.sections_json)
        sys.stderr = open(os.devnull, 'w')
        process_bar.progress(80)
        sys.stderr = sys.__stderr__

        for i,section in enumerate(self.sections_json):

            sys.stderr = open(os.devnull, 'w')
            process_text = f"Processing chapter：{i+1}/{total_sections}"
            process_bar.progress(80 + int(15 * (i/total_sections)), text=process_text)
            sys.stderr = sys.__stderr__

            if section["section"] == "0" or section["section"] == "-1":
                section_content = self._extract_captions(section["content"])
                self.sections_json[i]["trans_content"] = self._extract_envs(section_content)
                self.sections_json[i]["content"] = self.sections_json[i]["trans_content"]
            else:
                section_content = self._extract_captions(section["content"])
                self.sections_json[i]["content"] = self._extract_envs(section_content)

        sys.stderr = open(os.devnull, 'w')
        process_bar.progress(100, text="Finish Parse Sections")
        st.success("Finish Parse Sections")
        process_b.empty()
        sys.stderr = sys.__stderr__

    # def parse_no_env_cap_ph(self):
    #     """
    #     Parse the LaTeX document and return the parsed content.
    #     """
    #     main_tex_file = find_main_tex_file(self.dir) 
    #     if not main_tex_file:
    #         print("⚠️ Warning: There is no main tex file to compile in this directory.")
    #         return None
    #     main_tex = read_tex_file(main_tex_file)
    #     if not main_tex:
    #         print("⚠️ Warning: The main tex file is empty.")
    #         return None
        
    #     main_tex = remove_comments(main_tex)
    #     full_tex = self._merge_inputs(main_tex)
    #     full_tex = self._extract_newcommands(full_tex)
    #     full_tex = compress_newlines(full_tex)
    #     self._split_to_sections(full_tex)
    #     self._merge_short_sections(min_tokens=20)  # Merge short sections to avoid too many sections

    def _merge_inputs(self, tex: str) -> str:
        """
        Merge all the inputs in the main tex file and genarate a json file for the inputs.
        """
        main_tex = remove_comments(tex) 
        command_name = r'input|include'
        pattern_input = get_command_pattern(command_name) # \input{file.tex} or \input{file} or \include{file.tex} or \include{file}
        pos = 0
        while True:
            result = pattern_input.search(main_tex, pos)
            if result is None:
                break
            begin, end = result.span()
            pos = result.end()
            match = result.group(4)
            inputfilepath = os.path.join(self.dir, match)

            if os.path.exists(f'{inputfilepath}'):
                inputfilepath = f'{inputfilepath}'
            elif os.path.exists(f'{inputfilepath}.tex'):
                inputfilepath = f'{inputfilepath}.tex'
            else:
                print(f"⚠️ Warning: File not found: {inputfilepath}.tex or {inputfilepath}")
                pos = result.end()  # Skip this input and continue
                continue

            input_tex = read_tex_file(inputfilepath)
            input_tex = remove_comments(input_tex)
            input_begin = f"<PLACEHOLDER_{match}_begin>"
            input_end = f"<PLACEHOLDER_{match}_end>"
            input_tex = input_begin + input_tex + input_end
            main_tex = main_tex[:begin] + input_tex + main_tex[end:]
            self.inputs_json.append({
                "command": result.group(0),
                "begin": input_begin,
                "end": input_end,
                "path": match
            })

        return main_tex

    def _extract_envs(self, tex: str) -> str:
        """
        Extract all the environments in the full tex and generate a json file for the environments.
        The environments are replaced with placeholders in the full tex.
        """
        full_tex = remove_comments(tex)
        command_name = r'.*?'
        pattern_env = get_env_pattern(command_name) # \begin{env}...\end{env} or \begin{env}...\end{env}* or \begin{env}[options]...\end{env}
        placeholder_pattern_cap= r"<PLACEHOLDER_CAP_\d+>"
        no_translate_envs = [
                             'equation', 'align', 'align*', 'gather', 'gather*', 'verbatim', 'verbatim*', 'lstlisting*', 'minted', 'minted*',
                             'equation*', 'alignat', 'alignat*', 'flalign', 'flalign*', 'split', 'split*', 'cases', 'cases*', 'subequations', 
                             'figure', 'figure*', 'wrapfigure', 'SCfigure', 'tikzpicture', 'CJK', 'scope',
                             'tabularx', 'tabulary', 'longtable*', 'sidewaystable', 'table', 'table*', 'tabular', 'tabular*', 'longtable',
                             'multline', 'multline*', 'lstlisting', 'tcolorbox', 'thebibliography', 'bibliography', 'bibitem',
                             'algorithm', 'algorithmic', 'algorithmicx', 'algorithm2e', 'algorithmicx*', 'algorithmic*', 'algorithm*'
                             ]
        while True:
            result = pattern_env.search(full_tex)
            if result is None:
                break
            self.env_count += 1
            env_name = result.group(1)
            env_content = result.group(0)
            placeholders_cap_in_env = re.findall(placeholder_pattern_cap, env_content)

            need_trans = True

            if env_name in no_translate_envs:
                need_trans = False

            if placeholders_cap_in_env:
                # If there are placeholders in the environment, we do not translate it.
                need_trans = False

            placeholder = f"<PLACEHOLDER_ENV_{self.env_count}>"
            full_tex = full_tex.replace(env_content, placeholder, 1)
            self.envs_json.append({
                "placeholder": placeholder,
                "env_name": env_name,
                "content": env_content,
                "trans_content": '',
                "need_trans": need_trans
            })
        
        return full_tex

    def _extract_captions(self, tex: str) -> str:
        """
        Extract all the captions in the full tex and genarate a json file for the captions.
        The captions are replaced with placeholders in the full tex.
        """
        full_tex = remove_comments(tex)
        command_name = r'caption|caption\*|subcaption|subcaption\*|title|keywords|abstract|icmltitle|icmltitlerunning'
        pattern_caption = get_command_pattern(command_name) # \caption{...} or \caption*{...} or \caption[...]{...}
        pattern_captionof = get_captionof_pattern()

        while True:
            result = pattern_caption.search(full_tex)
            if result is None:
                break
            self.caption_count += 1
            placeholder = f"<PLACEHOLDER_CAP_{self.caption_count}>"
            full_tex = full_tex.replace(result.group(0), placeholder, 1)
            self.captions_json.append({
                "placeholder": placeholder,
                "cap_type":result.group(1),
                "content": result.group(0),
                "trans_content": ''
            })

        while True:
            result = pattern_captionof.search(full_tex)
            if result is None:
                break
            self.caption_count += 1
            placeholder = f"<PLACEHOLDER_CAP_{self.caption_count}>"
            full_tex = full_tex[:result.start()] + placeholder + full_tex[result.end():]
            self.captions_json.append({
                "placeholder": placeholder,
                "cap_type": result.group("command"),
                "content": result.group(0),
                "trans_content": '',
            })

        return full_tex
    
    def _extract_newcommands(self, tex: str) -> str:
        """
        Extract all the newcommands in the full tex and genarate a json file for the newcommands.
        """
        def get_nonNone(*args):
            result = [arg for arg in args if arg is not None]
            assert len(result) == 1
            return result[0]
        
        full_tex = remove_comments(tex)
        pattern = get_newcommand_pattern() # \newcommand{name}[n_arguments]{content} or \renewcommand{name}[n_arguments]{content} or 
                                           # \newenvironment{name}[n_arguments]{content} or \renewenvironment{name}[n_arguments]{content}
        count = 0
        
        while True:
            match = pattern.search(full_tex)
            if match is None:
                break
            name1 = match.group(1)
            name2 = match.group(2)
            name = get_nonNone(name1, name2)
            n_arguments = match.group(3)
            if n_arguments is None:
                n_arguments = 0
            else:
                n_arguments = int(n_arguments)
            placeholder = f"<PLACEHOLDER_NEWCOMMAND_{count}>"
            full_tex = full_tex.replace(match.group(0), placeholder, 1)
            self.newcommands_json.append({
                "placeholder": placeholder,
                "name": name,
                "content": match.group(0)
            })
            count += 1

        return full_tex
    
    def _split_to_sections(self, tex: str) -> Any:
        """
        Split the full tex to sections and genarate a json file for the sections.
        """
        full_tex = remove_comments(tex)
        command_name_section = r'section|subsection|subsubsection|section\*|subsection\*|subsubsection\*' # \chapter is not supported yet
        pattern_section = get_command_pattern(command_name_section) # \section{...} or \subsection{...} or \subsubsection{...}
        begin_document_pattern = get_begin_document_pattern() # \begin{document}
        begin_document_match = begin_document_pattern.search(full_tex)
        preamble = full_tex[:begin_document_match.start()] if begin_document_match else full_tex #...\begin{document}

        self.sections_json.append({
            "section": "-1",
            "content": preamble,
            "trans_content": preamble
        })

        document = full_tex[begin_document_match.start():] if begin_document_match else full_tex

        section_count = 0
        subsection_count = 0
        subsubsection_count = 0
        first_section_match = pattern_section.search(document)

        if not first_section_match: # no section found
            print("There is no section in the full tex.")
            self.sections_json.append({
                "section": "0",
                "content": document,
                "trans_content": ''
            })
            return

        before_section = document[:first_section_match.start()] if first_section_match else document # \begin{document}...\section{...}
        sections_tex = document[first_section_match.start():] if first_section_match else document
        
        self.sections_json.append({
            "section": "0",
            "content": before_section,
            "trans_content": before_section
        })

        last_pos = 0
        last_result = first_section_match

        for result in pattern_section.finditer(sections_tex):
            if last_pos != result.start():
                if last_result.group(1) == "section" or last_result.group(1) == "section*":
                    section_count += 1
                    subsection_count = 0
                    subsubsection_count = 0
                    self.sections_json.append({
                        "section": f'{section_count}',
                        "content": sections_tex[last_pos:result.start()],
                        "trans_content": ''
                    })
                elif last_result.group(1) == "subsection" or last_result.group(1) == "subsection*":
                    subsection_count += 1
                    subsubsection_count = 0
                    self.sections_json.append({
                        "section": f'{section_count}_{subsection_count}',
                        "content": sections_tex[last_pos:result.start()],
                        "trans_content": ''
                    })
                elif last_result.group(1) == "subsubsection" or last_result.group(1) == "subsubsection*":
                    subsubsection_count += 1
                    self.sections_json.append({
                        "section": f'{section_count}_{subsection_count}_{subsubsection_count}',
                        "content": sections_tex[last_pos:result.start()],
                        "trans_content": ''
                    })
            last_pos = result.start()
            last_result = result

        if last_result.group(1) == "section" or last_result.group(1) == "section*":
            section_count += 1
            subsection_count = 0
            subsubsection_count = 0
            self.sections_json.append({
                "section": f'{section_count}',
                "content": sections_tex[last_pos:],
                "trans_content": ''
            })
        elif last_result.group(1) == "subsection" or last_result.group(1) == "subsection*":
            subsection_count += 1
            subsubsection_count = 0
            self.sections_json.append({
                "section": f'{section_count}_{subsection_count}',
                "content": sections_tex[last_pos:],
                "trans_content": ''
            })
        elif last_result.group(1) == "subsubsection" or last_result.group(1) == "subsubsection*":
            subsubsection_count += 1
            self.sections_json.append({
                "section": f'{section_count}_{subsection_count}_{subsubsection_count}',
                "content": sections_tex[last_pos:],
                "trans_content": ''
            })

    def _merge_short_sections(self, min_tokens=20):
        """
        Merge sections that are too short to save the number of api requests
        """
        enc = tiktoken.encoding_for_model("gpt-4")
        merged_sections = []
        i = 0
        sections = self.sections_json

        while i < len(sections):
            combined_content = sections[i]["content"]
            combined_section_ids = [sections[i]["section"]]
            total_tokens = len(enc.encode(combined_content))
            start_section = sections[i]
            j = i + 1

            while total_tokens < min_tokens and j < len(sections):
                combined_content += "\n" + sections[j]["content"]
                combined_section_ids.append(sections[j]["section"])
                total_tokens = len(enc.encode(combined_content))
                j += 1

            if total_tokens < min_tokens and len(merged_sections) > 0:
                merged_sections[-1]["content"] += "\n" + combined_content
                merged_sections[-1]["section"] += "+" + "+".join(combined_section_ids)
                print(merged_sections[-1]["section"])
            else:
                merged_section = start_section.copy()
                merged_section["content"] = combined_content
                merged_section["section"] = "+".join(combined_section_ids)
                merged_sections.append(merged_section)

            i = j

        self.sections_json = merged_sections

        
