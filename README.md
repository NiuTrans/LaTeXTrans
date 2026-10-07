<div align="center">

English | [中文](README_ZH.md)


<img src="./logo.png" width="1000px"></img>

  **Turn arXiv Papers into Multilingual Masterpieces**
#
<!-- <p align="center">
  <a href="https://arxiv.org/abs/2503.06594" alt="paper"><img src="https://img.shields.io/badge/Paper-LaTeXTrans-blue?logo=arxiv&logoColor=white"/></a>
</p> -->

</div>

<div align="center">
<p dir="auto">

• 📖 [Introduction](#-introduction) 
• 🛠️ [Installation Guide](#️-installation-guide) 
• ⚙️ [Configuration Guide](#️-configuration-guide)
• 📚 [Usage](#-Usage)
• 🖼️ [Translation Examples](#️-translation-examples) 

</p>
</div>

 End-to-end translation from arXiv paper ID to translated PDF. LaTeXTrans have the following **Features** :
 - **🌟 Preserve the integrity of formulas, layout, and cross-references**
 - **🌟 Ensure consistency in terminology translation**
 - **🌟 Support end-to-end conversion from original TeX source (automatically downloaded based on the arXiv paper id provided) to translated PDF**

With LaTeXTrans, researchers and students can obtain higher-quality arXiv paper translations without worrying about formatting confusion or missing content, thus reading and understanding arXiv papers more efficiently.

# 📖 Introduction

LaTeXTrans is a structured LaTeX document translation system based on multi-agent collaboration. It directly translates LaTeX code and generates translated PDFs with high fidelity to the original layout. Unlike traditional document translation methods (e.g., PDF translation), which often break formulas and formatting, LaTeXTrans leverages LLM to translate preprocessed LaTeX sources and employs a workflow composed of six agents—Parser, Translator, Validator, Summarizer, Terminology Extractor, and Generator to achieve the features. The figure below illustrates the system architecture of LaTeXTrans. 
<!-- For a more detailed introduction, please refer to our published paper 🔗 [LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination](https://arxiv.org/abs/2508.18791). -->

<!-- <img src="./main-figure.jpg" width="1000px"></img> -->


# 🛠️ Installation Guide

#### 1. Clone Repository

```bash
git clone https://github.com/NiuTrans/LaTeXTrans.git
cd LaTeXTrans
pip install -e .
```

#### (Optional) Use Conda Environment

```bash
conda create -n latextrans python=3.10 -y
conda activate latextrans
git clone https://github.com/NiuTrans/LaTeXTrans.git
cd LaTeXTrans
pip install -e .
```

#### 2. Install MikTex(Recommended) or TeXLive

If you need to compile LaTeX files (e.g., generate PDF output), install [MikTex](https://miktex.org/download) or [TeXLive](https://www.tug.org/texlive/) !

 > [!IMPORTANT]
For MikTex, installation please be sure to select "install on the fly", in addition, you need to install additional [Strawberry Perl](http://strawberryperl.com/) support compilation.

# ⚙️ Configuration Guide

### Local Configuration

Please edit the configuration file before use:

```arduino
config/default.toml
```

Set the language model's API key and base URL in default.toml :

```toml
model = " " # model name (For example, deepseek-chat)
api_key = " " # your_api_key_here
base_url = " " # base url of the API (For example, https://api.deepseek.com/v1/chat/completions)
timeout = 100 # LLM request timeout in seconds (default: 100)
concurrency_limit = 4 # lower this when your provider returns HTTP 429 (default: 10)
```

`concurrency_limit` must be a positive integer and applies to translation and retranslation tasks within each project. Requests retry temporary HTTP 429/502/503/504 and connection/time-out failures up to three total attempts. Retries honor `Retry-After` seconds or HTTP dates; without it, they wait 5 then 10 seconds. Permanent HTTP errors such as 401 stop immediately.

 > [!NOTE]
The following example shows the recommended base_url for different models:

| Model |base_url| 
|:-|:-|
|deepseek-chat|https://api.deepseek.com/v1/chat/completions|
|gpt-4o|https://api.openai.com/v1/chat/completions|
|gemini-2.5-pro|https://generativelanguage.googleapis.com/v1beta/openai/chat/completions|

# 📚 Usage

###  Translation via ArXiv ID 

Simply provide an arXiv paper ID to complete translation:

```bash
latextrans --arxiv ${xxxx}
# For example, 
# latextrans --arxiv 2508.18791
```

Versioned arXiv IDs are also supported, so you can target a specific revision:

```bash
latextrans --arxiv 2508.18791v2
```

This command will:

1. Download the LaTeX source code from arXiv and extract it
2. Execute a workflow consisting of parsing, translation, refactoring and compilation
3. Save the translated LaTeX project file of the paper and the PDF of the compiled translation in the outputs folder

### Batch Translation via ArXiv IDs

You can translate multiple arXiv papers in one run (comma-separated):

```bash
latextrans --arxiv ${xxxx}, ${xxxx}
# For example,
# latextrans --arxiv 2508.18791v2, 2407.01648
```

### Translation via Local Project

You can also pass a local compressed source package directly:

```bash
latextrans --project D:\\path\\to\\paper_source.tar.gz
```

Or pass a local extracted project directory:

```bash
latextrans --project D:\\path\\to\\paper_project_dir
```

When you provide `--arxiv` or `--project`, LaTeXTrans only processes those explicit inputs.
Existing folders under `tex source` are ignored in this mode.

To process every existing project under `tex source`, run:

```bash
latextrans --all-existing
```

### GUI via Streamlit

If you want a browser-based GUI with live workflow progress, logs, and runtime configuration, launch:

```bash
latextrans-gui
```

Or run Streamlit directly:

```bash
streamlit run src/gui/streamlit_app.py
```

 > [!NOTE]
Although LaTeXTrans supports translation from any language to any language, the current version has only made relatively complete compilation adaptations for translation from English to Chinese. When translating to other languages, the final output pdf may contain errors. We welcome you to raise an issue to describe the problem you have encountered, and we will solve it case by case.

<!-- # 🧰 Experimental Results

| System | COMETkiwi | LLM-score | FC-score | Cost |
|:-|:-:|:-:|:-:|:-:|
|NiuTrans |64.69|7.93|60.72|-|
|Google Translate |46.23|5.93|51.00|-|
|LLaMA-3.1-8b|42.89|2.92|49.40|-|
|Qwen-3-8b|45.55|7.87|48.68|-|
|Qwen-3-14b|68.18|8.76|65.63|-|
|DeepSeek-V3|67.26|**9.02**|63.68|$0.02|
|GPT-4o|67.22|8.58|58.32|$0.13|
|**LaTeXTrans(Qwen-3-14b)**|71.37|8.97|71.20|-|
|**LaTeXTrans(DeepSeek-V3)**|73.48|9.01|70.52|$0.10|
|**LaTeXTrans(GPT-4o)**|**73.59**|8.92|**71.52**|$0.35|

Note:
- **COMETkiwi** : a quality estimation model ([wmt22-cometkiwi-da](https://huggingface.co/Unbabel/wmt22-cometkiwi-da)) that reflects the quality of the translation, the higher the score, the better the translation quality.
- **LLM-score** : a method for evaluating the quality of translation using LLM (GPT-4o), the higher the score, the better the translation quality.
- **FC-score** : a method proposed in our paper to evaluate the formatting ability of LaTeX translation by detecting the number of errors in the compiled logs, the higher the score, the better the ability to maintain format.
- **Cost** : the average cost of translating each paper using the official API. -->
  


# 🖼️ Translation Examples

The following are four real translation examples generated by **LaTeXTrans**, with the original text on the left and translation results on the right.

### 📄 Case 1 ( en->ch ) :

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples/case1src.png" width="100%"></td>
    <td><img src="examples/case1ch.png" width="100%"></td>
  </tr>
</table>

### 📄 Case 2 ( en->ch ):

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples/case3src.png" width="100%"></td>
    <td><img src="examples/case3ch.png" width="100%"></td>
  </tr>
</table>

### 📄 Case 3 ( en->jp ):

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples\case-en.png" width="100%"></td>
    <td><img src="examples\case-jp.png" width="100%"></td>
  </tr>
</table>

### 📄 Case 4 ( en->jp ):

<table>
  <tr>
    <td align="center"><b>Original</b></td>
    <td align="center"><b>Translation</b></td>
  </tr>
  <tr>
    <td><img src="examples\case5a-1-en.png" width="100%"></td>
    <td><img src="examples\case5b-1-jp.png" width="100%"></td>
  </tr>
</table>

📂 **See [`examples/`](examples/) folder for more cases**, including complete translation PDFs for each case.

---
## Acknowledgments

We would like to thank all the students who contributed to this project：
Haosong Xv, Yiyang Liu, Heng Zhang, Xiaoru Huang, Yihang Zhang, Ce Liu, Shuochang Zhang, Jihang Yv, Boyang Liu.

---
## Citation
```bash
@article{zhu2025latextrans,
  title={LaTeXTrans: Structured LaTeX Translation with Multi-Agent Coordination},
  author={Zhu, Ziming and Wang, Chenglong and Xing, Shunjie and Huo, Yifu and Tian, Fengning and Du, Quan and Yang, Di and Zhang, Chunliang and Xiao, Tong and Zhu, Jingbo},
  journal={arXiv preprint arXiv:2508.18791},
  year={2025}
}
