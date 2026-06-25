#  ComfyUI Script-to-Video Suite

> Transform PDF scripts into AI-ready video generation prompts through an intelligent  pipeline.

A  ComfyUI custom node suite that converts long-form PDF scripts into structured storyboards and detailed video generation prompts using AI-powered parsing and scene breakdown.


---

## Badges

![ComfyUI](https://img.shields.io/badge/ComfyUI-Compatible-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Status](https://img.shields.io/badge/Status-Active-success)

---

## Table of Contents

- [Features](#-features)
- [Installation & Setup](#-installation--setup)
- [Architecture Overview](#-architecture-overview)
- [Script-to-Video Pipeline](#-script-to-video-pipeline)
- [Node Reference](#-node-reference)
- [Example Usage](#-example-usage)
- [Development Guide](#-development-guide)
- [Maintainers & Acknowledgements](#-maintainers--acknowledgements)

---

## Features

-  **PDF Script Processing**: Extract and chunk text from PDF screenplay/script files with path-based or upload-based input
- **AI-Powered Storyboarding**: Generate detailed storyboard panels using Gemini AI via relay server
- **Prompt Engineering**: Convert storyboard scenes into optimized video generation prompts
- **Modular Pipeline**: Independent, chainable nodes for maximum flexibility
- **ComfyUI Integration**: Seamless workflow integration with custom output types


---

##  Installation & Setup

### Prerequisites

- **ComfyUI** (latest version recommended)
- **Python 3.10+**
- **PyMuPDF** for PDF processing
- **Git** 

### Installation Steps

1. **Clone the repository** into your ComfyUI custom nodes directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/Long-form-AI-video-generation/script-parser-custom-node.git
```

2. **Install dependencies**:

```bash
cd script-parser-custom-node
cd comfyui_script_to_video_suite
pip install -r requirements.txt
```

3. **Restart ComfyUI** to load the custom nodes

4. **Verify installation** - Look for "Script To Video Suite" in your node menu

### Relay Server Configuration

The suite uses a Gemini AI relay server for processing. The default endpoint is pre-configured. 
This was required because API usage is restricted in some location and if it is needed to abstract the API calls in another location.

Steps
1. clone the gemeni relay repository. `git clone https://github.com/bisratberhanu/gemini-relay.git`
2. set your gemeni api key in the environment variable. 
3. run the server by running `GEMINI_API_KEY="your-gemeni-api-key" gunicorn --bind 127.0.0.1:8080 --timeout 700 app:app`
4. In a new terminal run the command `ngrok http 8080`. make sure ngrok is installed on your computer.
5. copy the server location it will look some thing like `https://unique-name.ngrok-free.dev`
6. copy `.env.example` to `.env` in this repository:
   ```bash
   cp .env.example .env
### Troubleshooting

- **Nodes not appearing in ComfyUI:**  
  Ensure the repository is cloned into `ComfyUI/custom_nodes/` and restart ComfyUI.
- **Relay server connection errors:**  
  Check your internet connection and verify that `RELAY_SERVER_URL` is correctly set in your environment or in the `.env` file used by this project.



---

##  Architecture Overview

### System Design

```
┌─────────────────┐
│   PDF Script    │
│    (Input)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   1. PDF Chunker        │
│   - Extract text        │
│   - Create overlapping  │
│     chunks              │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 2. Storyboard Generator │
│   - Process via Gemini  │
│   - Create panels       │
│   - De-duplicate        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 3. Prompt Generator     │
│   - Split into scenes   │
│   - Generate prompts    │
│   - Format for AI video │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────────────────
│                                     │
│ Video Prompts and iamge prompts     │
│   (Output)                          │
└─────────────────┘────────────────────
```

---

##  Script-to-Video Pipeline

### Stage 1: PDF Chunking

The **PDF Chunker** nodes extract text from PDF files and split it into manageable chunks with configurable overlap to maintain context between segments.

**Key Parameters:**
- `pdf_path`: File path to the source PDF script
- `pdf_file`: Uploaded PDF from the ComfyUI input folder, used by the upload variant
- `chunk_size`: Characters per chunk (4000)
- `overlap_size`: Overlap between chunks (400) 

### Stage 2: Storyboard Generation

The **Storyboard Generator** processes each chunk through the Gemini relay server to create detailed storyboard panels with visual descriptions and action notes.

**Processing Flow:**
1. Iterates through text chunks
2. Sends each chunk with prompt template to relay server
3. Collects AI-generated storyboard panels
4. De-duplicates based on action descriptions 

### Stage 3: Prompt Generation

The **Prompt Generator** converts storyboard scenes into detailed, AI-ready video generation prompts optimized for models like Stable Diffusion Video or RunwayML.

**Scene Processing:**

---

##  Node Reference

### 1. PDF Chunker (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `pdf_path` (STRING), `chunk_size` (INT), `overlap_size` (INT) |
| **Output Type** | `CHUNKS` (custom type) |
| **Function** | `process_pdf` |

**Purpose**: Extracts and chunks PDF script text for processing 

---

### 1a. PDF Upload Chunker (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `pdf_file` (PDF upload/select), `chunk_size` (INT), `overlap_size` (INT) |
| **Output Type** | `CHUNKS`, `STRING`, `INT` |
| **Function** | `process_uploaded_pdf` |

**Purpose**: Uploads or selects a PDF from ComfyUI's input folder, then returns the same chunk outputs as the path-based PDF Chunker.

---

### 2. Storyboard Generator (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `chunks` (CHUNKS), `prompt_template` (STRING) |
| **Output Type** | `STRING` (storyboard_text) |
| **Function** | `generate_storyboard` |

**Purpose**: Converts script chunks into structured storyboard panels using AI 

---

### 3. Prompt Generator (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `storyboard_text` (STRING), `prompt_template` (STRING) |
| **Output Type** | `STRING` (final_prompts) |
| **Function** | `generate_prompts` |

**Purpose**: Generates AI video generation prompts from storyboard scenes 

---

##  Example Usage

### Basic Workflow

```
[PDF Chunker or PDF Upload Chunker] → [Storyboard Generator] → [Prompt Generator] → [Save Text]
```

### Workflow Configuration

1. **Add a PDF input node**
   ```
   pdf_path: "C:/Scripts/my_screenplay.pdf"
   chunk_size: 4000
   overlap_size: 400
   ```
   Or use **PDF Upload Chunker (S2V)** and choose a PDF from the upload button.

2. **Connect to Storyboard Generator**

3. **Connect to Prompt Generator**
   

### Sample Output Format

```
--- SCENE BREAK ---

PANEL 001
ACTION_DESCRIPTION: Character walks through foggy street at night
VISUAL_PROMPT: cinematic shot, noir atmosphere, streetlights through fog, 
lone figure silhouette, moody lighting, 4k quality

--- SCENE BREAK ---

PANEL 002
ACTION_DESCRIPTION: Close-up of character's face showing concern
VISUAL_PROMPT: dramatic close-up, concerned expression, rim lighting, 
shallow depth of field, cinematic color grading
```

---

##  Development Guide

### Project Structure

```
script-parser-custom-node/
└── comfyui-script-to-video-suite/
    ├── __init__.py                    # Node registration
    └── s2v_nodes/
        ├── gemini_relay_client.py     # API relay client
        ├── pdf_parser_node.py         # Legacy parser 
        ├── s2v_chunker_node.py        # PDF Chunker node
        ├── s2v_storyboard_node.py     # Storyboard Generator
        └── s2v_prompt_gen_node.py     # Prompt Generator
        and more nodes
```

### Dependencies

- **PyMuPDF (fitz)**: PDF text extraction
- **requests**: HTTP communication with relay server
- **re**: Regular expression for scene parsing
- **json**: Data serialization

### Environment Setup

1. **Development Installation**:
```bash
git clone https://github.com/Long-form-AI-video-generation/script-parser-custom-node.git
cd script-parser-custom-node
pip install -e .
```

2. **Testing Nodes**:
    - Load ComfyUI in development mode
    - Add nodes to test workflow
    - Monitor console output for debugging

---



### Reporting Issues

- Use GitHub Issues for bug reports
- Include ComfyUI version, Python version, and error logs
- Provide sample PDF or workflow JSON if applicable

---

##  Maintainers & Acknowledgements

### Maintainers

**Long-form AI Video Generation Team**
- Repository: [Long-form-AI-video-generation](https://github.com/Long-form-AI-video-generation)




---


---
<p align="center">
 <i>Contributions, feedback, and ideas are always welcome! </i>
</p>
<div align="center">

**⭐ If this project helps your workflow, consider giving it a star! ⭐**

</div>
