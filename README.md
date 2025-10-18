# ComfyUI Script-to-Video Suite

> Transform PDF scripts into AI-ready video generation prompts through an intelligent three-stage pipeline

A powerful ComfyUI custom node suite that converts long-form PDF scripts into structured storyboards and detailed video generation prompts using AI-powered parsing and scene breakdown.

---

## Badges

![ComfyUI](https://img.shields.io/badge/ComfyUI-Compatible-brightgreen)![Python](https://img.shields.io/badge/Python-3.10+-blue)![License](https://img.shields.io/badge/License-MIT-yellow)![Status](https://img.shields.io/badge/Status-Active-success)

---

## Table of Contents

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

## Features

-   **PDF Script Processing**: Extract and chunk text from PDF screenplay/script files with configurable overlap.
-   **AI-Powered Storyboarding**: Generate detailed storyboard panels using Gemini AI via a relay server.
-   **Prompt Engineering**: Convert storyboard scenes into optimized video generation prompts.
-   **Modular Pipeline**: Three independent, chainable nodes for maximum flexibility.
-   **ComfyUI Integration**: Seamless workflow integration with custom output types.
-   **Zero API Key Configuration**: All AI processing is handled by a secure relay server, so you never have to manage or expose your own API keys.

---

## Installation & Setup

### Prerequisites

-   **ComfyUI** (latest version recommended)
-   **Python 3.10+**
-   **Git**

### Installation Steps

1.  **Clone the repository** into your ComfyUI `custom_nodes` directory:

    ```bash
    cd /path/to/ComfyUI/custom_nodes/
    git clone https://github.com/Long-form-AI-video-generation/script-parser-custom-node.git comfyui-script-to-video-suite
    ```

2.  **Install dependencies** using the provided `requirements.txt` file:
    > **Note:** We recommend creating a `requirements.txt` file in the root of the repository with the content below for a stable installation.

    ```bash
    cd comfyui-script-to-video-suite
    pip install -r requirements.txt
    ```
    Your `requirements.txt` file should contain:
    ```
    PyMuPDF
    requests
    ```

3.  **Restart ComfyUI** completely to load the custom nodes.

4.  **Verify installation** - Look for the "Script To Video Suite" category in your node menu.

### Relay Server Configuration

The suite uses a Gemini AI relay server for processing. The default endpoint is pre-configured.

To use your own relay server, update the `RELAY_SERVER_URL` in `s2v_nodes/gemini_relay_client.py`.

###  Troubleshooting

-   **Nodes not appearing in ComfyUI:**
    Ensure the repository is cloned into `ComfyUI/custom_nodes/` and you have restarted ComfyUI completely.
-   **Relay server connection errors:**
    Check your internet connection and verify the `RELAY_SERVER_URL` in the client file.
-   **PDF parsing issues:**
    Confirm that the PDF is not encrypted or purely image-based (it must contain selectable text).

---

## Architecture Overview

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

### Core Components

The suite registers three primary nodes with ComfyUI's node system, each designed for a specific stage of the script-to-video conversion pipeline.

---

## Script-to-Video Pipeline

### Stage 1: PDF Chunking

The **PDF Chunker** node extracts text from PDF files and splits it into manageable chunks with configurable overlap to maintain context between segments.

**Key Parameters:**

-   `pdf_path`: File path to the source PDF script
-   `chunk_size`: Characters per chunk (4000)
-   `overlap_size`: Overlap between chunks (400)

### Stage 2: Storyboard Generation

The **Storyboard Generator** processes each chunk through the Gemini relay server to create detailed storyboard panels with visual descriptions and action notes.

**Processing Flow:**

1.  Iterates through text chunks
2.  Sends each chunk with a prompt template to the relay server
3.  Collects AI-generated storyboard panels
4.  De-duplicates panels based on action descriptions to avoid repetition

### Stage 3: Prompt Generation

The **Prompt Generator** converts storyboard scenes into detailed, AI-ready video generation prompts optimized for models like Stable Diffusion Video or RunwayML.

**Scene Processing:** Parses the generated storyboard into individual scenes before sending them to the AI for final prompt creation.

---

## Node Reference

### 1. PDF Chunker (S2V)

| Property      | Description                                                    |
| :------------ | :------------------------------------------------------------- |
| **Category**  | Script To Video Suite                                          |
| **Input Types** | `pdf_path` (STRING), `chunk_size` (INT), `overlap_size` (INT) |
| **Output Type** | `CHUNKS` (custom type)                                         |
| **Function**  | `process_pdf`                                                  |

**Purpose**: Extracts and chunks PDF script text for processing.

---

### 2. Storyboard Generator (S2V)

| Property      | Description                                        |
| :------------ | :------------------------------------------------- |
| **Category**  | Script To Video Suite                              |
| **Input Types** | `chunks` (CHUNKS), `prompt_template` (STRING)      |
| **Output Type** | `STRING` (storyboard_text)                         |
| **Function**  | `generate_storyboard`                              |

**Purpose**: Converts script chunks into structured storyboard panels using AI.

---

### 3. Prompt Generator (S2V)

| Property      | Description                                          |
| :------------ | :--------------------------------------------------- |
| **Category**  | Script To Video Suite                                |
| **Input Types** | `storyboard_text` (STRING), `prompt_template` (STRING) |
| **Output Type** | `STRING` (final_prompts)                             |
| **Function**  | `generate_prompts`                                   |

**Purpose**: Generates AI video generation prompts from storyboard scenes.

---

## Example Usage

### Basic Workflow

```
[PDF Chunker] → [Storyboard Generator] → [Prompt Generator] → [Save Text]
```

### Workflow Configuration

1.  **Add PDF Chunker Node**

    ```text
    pdf_path: "C:/Scripts/my_screenplay.pdf"
    chunk_size: 4000
    overlap_size: 400
    ```

2.  **Connect to Storyboard Generator**

    ```text
    prompt_template: "You are a storyboard artist. Create storyboard
    panels from the following script text. Use '--- PANEL BREAK ---'
    between panels..."
    ```

3.  **Connect to Prompt Generator**

    ```text
    prompt_template: "You are a prompt engineer for an AI video generator.
    Convert the following storyboard scene into detailed prompts..."
    ```

### Sample Output Format

```text
--- SCENE BREAK ---

PANEL 001
ACTION_DESCRIPTION: Character walks through foggy street at night
VISUAL_PROMPT: cinematic shot, noir atmosphere, streetlights through fog,
lone figure silhouette, moody lighting, 4k quality

--- SCENE BREAK ---
```

---

## 🛠️ Development Guide

### Project Structure

```text
comfyui-script-to-video-suite/
├── __init__.py                    # Node registration
├── requirements.txt               # Dependencies
└── s2v_nodes/
    ├── __init__.py                # Marks as Python package
    ├── gemini_relay_client.py     # API relay client
    ├── s2v_chunker_node.py        # 1. PDF Chunker node
    ├── s2v_storyboard_node.py     # 2. Storyboard Generator
    └── s2v_prompt_gen_node.py     # 3. Prompt Generator
    └── pdf_parser_node.py         # Legacy/unused node
```
*Note: `pdf_parser_node.py` is an un-registered legacy file and is not used in the primary workflow.*

### Dependencies

-   **PyMuPDF (fitz)**: PDF text extraction
-   **requests**: HTTP communication with the relay server

### Environment Setup

1.  **Development Installation**:
    ```bash
    git clone https://github.com/Long-form-AI-video-generation/script-parser-custom-node.git
    cd script-parser-custom-node
    pip install -e .
    ```

2.  **Testing Nodes**:
    -   Load ComfyUI and create a workflow to test the nodes.
    -   Monitor the console output for print statements and debugging information.

---

## Maintainers & Acknowledgements

### Maintainers

**Long-form AI Video Generation Team**

-   Repository: [script-parser-custom-node](https://github.com/Long-form-AI-video-generation/script-parser-custom-node)

### Acknowledgements

-   **ComfyUI Team** - For the extensible workflow framework.
-   **Google Gemini** - For AI-powered text generation capabilities.
-   **Open Source Community** - For continuous support and feedback.

### Related Projects

-   [ComfyUI](https'github.com/comfyanonymous/ComfyUI) - The powerful GUI that makes this project possible.

---

<p align="center">
 <i>Contributions, feedback, and ideas are always welcome! Let’s build the future of AI video together!</i>
</p>
<div align="center">

**⭐ If this project helps your workflow, consider giving it a star! ⭐**

[⬆ Back to Top](#ComfyUI-Script-to-Video-Suite)

</div>