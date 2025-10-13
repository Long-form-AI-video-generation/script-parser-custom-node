# 📄 ComfyUI Script-to-Video Suite

> Transform PDF scripts into AI-ready video generation prompts through an intelligent three-stage pipeline

A powerful ComfyUI custom node suite that converts long-form PDF scripts into structured storyboards and detailed video generation prompts using AI-powered parsing and scene breakdown.

---

## 🏷️ Badges

![ComfyUI](https://img.shields.io/badge/ComfyUI-Compatible-brightgreen)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Status-Active-success)

---

## 📋 Table of Contents

- [Features](#-features)
- [Installation & Setup](#-installation--setup)
- [Architecture Overview](#-architecture-overview)
- [Script-to-Video Pipeline](#-script-to-video-pipeline)
- [Node Reference](#-node-reference)
- [Example Usage](#-example-usage)
- [Development Guide](#-development-guide)
- [Contributing](#-contributing)
- [License](#-license)
- [Maintainers & Acknowledgements](#-maintainers--acknowledgements)

---

##  Features

- ** PDF Script Processing**: Extract and chunk text from PDF screenplay/script files with configurable overlap
- ** AI-Powered Storyboarding**: Generate detailed storyboard panels using Gemini AI via relay server
- ** Prompt Engineering**: Convert storyboard scenes into optimized video generation prompts
- ** Modular Pipeline**: Three independent, chainable nodes for maximum flexibility
- ** ComfyUI Integration**: Seamless workflow integration with custom output types
- ** Relay Server Architecture**: Secure API access through dedicated relay endpoint

---

##  Installation & Setup

### Prerequisites

- **ComfyUI** (latest version recommended)
- **Python 3.10+**
- **PyMuPDF** for PDF processing
- **requests** library for API communication

### Installation Steps

1. **Clone the repository** into your ComfyUI custom nodes directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/Long-form-AI-video-generation/script-parser-custom-node.git
```

2. **Install dependencies**:

```bash
cd script-parser-custom-node
pip install PyMuPDF requests
```

3. **Restart ComfyUI** to load the custom nodes

4. **Verify installation** - Look for "Script To Video Suite" in your node menu

### Relay Server Configuration

The suite uses a Gemini AI relay server for processing. The default endpoint is pre-configured: [1](#0-0) 

To use your own relay server, update the `RELAY_SERVER_URL` in the gemini_relay_client.py file.

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
┌─────────────────┐
│ Video Prompts   │
│   (Output)      │
└─────────────────┘
```

### Core Components [2](#0-1) 

The suite registers three primary nodes with ComfyUI's node system, each designed for a specific stage of the script-to-video conversion pipeline.

---

##  Script-to-Video Pipeline

### Stage 1: PDF Chunking

The **PDF Chunker** node extracts text from PDF files and splits it into manageable chunks with configurable overlap to maintain context between segments.

**Key Parameters:**
- `pdf_path`: File path to the source PDF script
- `chunk_size`: Characters per chunk (100-16000)
- `overlap_size`: Overlap between chunks (0-8000) [3](#0-2) 

### Stage 2: Storyboard Generation

The **Storyboard Generator** processes each chunk through the Gemini relay server to create detailed storyboard panels with visual descriptions and action notes.

**Processing Flow:**
1. Iterates through text chunks
2. Sends each chunk with prompt template to relay server
3. Collects AI-generated storyboard panels
4. De-duplicates based on action descriptions [4](#0-3) 

### Stage 3: Prompt Generation

The **Prompt Generator** converts storyboard scenes into detailed, AI-ready video generation prompts optimized for models like Stable Diffusion Video or RunwayML.

**Scene Processing:** [5](#0-4) 

---

##  Node Reference

### 1. PDF Chunker (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `pdf_path` (STRING), `chunk_size` (INT), `overlap_size` (INT) |
| **Output Type** | `CHUNKS` (custom type) |
| **Function** | `process_pdf` |

**Purpose**: Extracts and chunks PDF script text for processing [6](#0-5) 

---

### 2. Storyboard Generator (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `chunks` (CHUNKS), `prompt_template` (STRING) |
| **Output Type** | `STRING` (storyboard_text) |
| **Function** | `generate_storyboard` |

**Purpose**: Converts script chunks into structured storyboard panels using AI [7](#0-6) 

---

### 3. Prompt Generator (S2V)

| Property | Description |
|----------|-------------|
| **Category** | Script To Video Suite |
| **Input Types** | `storyboard_text` (STRING), `prompt_template` (STRING) |
| **Output Type** | `STRING` (final_prompts) |
| **Function** | `generate_prompts` |

**Purpose**: Generates AI video generation prompts from storyboard scenes [8](#0-7) 

---

##  Example Usage

### Basic Workflow

```
[PDF Chunker] → [Storyboard Generator] → [Prompt Generator] → [Save Text]
```

### Workflow Configuration

1. **Add PDF Chunker Node**
   ```
   pdf_path: "C:/Scripts/my_screenplay.pdf"
   chunk_size: 4000
   overlap_size: 400
   ```

2. **Connect to Storyboard Generator**
   ```
   prompt_template: "You are a storyboard artist. Create storyboard 
   panels from the following script text. Use '--- PANEL BREAK ---' 
   between panels..."
   ```

3. **Connect to Prompt Generator**
   ```
   prompt_template: "You are a prompt engineer for an AI video generator. 
   Convert the following storyboard scene into detailed prompts..."
   ```

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
        ├── pdf_parser_node.py         # Legacy parser (deprecated)
        ├── s2v_chunker_node.py        # PDF Chunker node
        ├── s2v_storyboard_node.py     # Storyboard Generator
        └── s2v_prompt_gen_node.py     # Prompt Generator
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

### Relay Server Communication [9](#0-8) 

---

##  Contributing

We welcome contributions to improve the Script-to-Video Suite! Here's how you can help:

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/some-feature`)
3. **Commit your changes** (`git commit -m 'Add feature'`)
4. **Push to the branch** (`git push origin feature/some-feature`)
5. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Add docstrings to all functions
- Test with various PDF formats
- Ensure ComfyUI compatibility
- Update documentation for new features

### Reporting Issues

- Use GitHub Issues for bug reports
- Include ComfyUI version, Python version, and error logs
- Provide sample PDF or workflow JSON if applicable

---

##  License

This project is licensed under the **MIT License** - see the LICENSE file for details.

---

##  Maintainers & Acknowledgements

### Maintainers

**Long-form AI Video Generation Team**
- Repository: [script-parser-custom-node](https://github.com/Long-form-AI-video-generation/script-parser-custom-node)

### Acknowledgements

- **ComfyUI Team** - For the extensible workflow framework
- **Google Gemini** - For AI-powered text generation capabilities
- **PyMuPDF Contributors** - For reliable PDF processing
- **Open Source Community** - For continuous support and feedback

### Related Projects

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - The AI workflow framework
- [ComfyUI-Manager](https://github.com/ltdrdata/ComfyUI-Manager) - Node package manager

---

<div align="center">

**⭐ If this project helps your workflow, consider giving it a star! ⭐**

</div>

---
