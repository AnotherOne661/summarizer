# AI PDF Summarizer (RAG)

A complete application that allows you to upload PDF documents, extract their content via OCR, and generate intelligent summaries or answer questions about the content using a local language model (Ollama) and semantic search (RAG with ChromaDB).

##  Features

- **Integrated OCR** - Reads text from scanned PDFs and images
- **RAG (Retrieval-Augmented Generation)** - Precise semantic search without hallucinations
- **Intelligent Summaries** - Generates coherent summaries of long documents
- **Question & Answer** - Ask specific questions about the content
- **Dark/Light Mode** - Adaptable interface with manual toggle
- **TXT Download** - Export summaries to text files
- **Docker & Local** - Run with Docker or directly on your machine

## 📋 Requirements

### For Docker execution
- Docker and Docker Compose
- (Optional) NVIDIA GPU with drivers and nvidia-container-toolkit

### For local execution
- Python 3.10+
- Node.js 18+
- Tesseract OCR
- Poppler-utils
- Ollama

##  Docker Execution

### 1. Clone the repository
```bash
git clone <this reposirory>
cd summarizer
```

### 2. Configure your enviroment variables (optional)
Edit docker-compose.yaml to change the Ollama model:
```yaml
environment:
  - OLLAMA_MODEL=llama3.2:3b  # Change to your preferred model
```
### 3. Start the containers
```bash
docker-compose up --build
```
### 4. Access the application
* Frontend: http://localhost:3000
* Backend API: http://localhost:8000
* API Documentation: http://localhost:8000/docs

### 5. Use GPU (Optional)
If you have an NVIDIA GPU, uncomment the lines in docker-compose.yaml:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```
## Local execution (WIP)

### 1. Clone the repository
```bash
git clone <your-repository>
cd summarizer
```
### 2. Run the automatic installation script
```bash
chmod +x setup_and_run.sh
./setup_and_run.sh
```
This script will automatically install:

* System dependencies (Tesseract, Poppler)

* Ollama and the llama3.2:3b model

* Python virtual environment with all dependencies

* Node.js and frontend dependencies

* Required configuration files
### 3. Run the application
```bash
./run_local.sh
```
### 4. Access the application
* Frontend: http://localhost:3000
* Backend API: http://localhost:8000
* API Documentation: http://localhost:8000/docs
### 5. Stop the application
Press Ctrl+C in the terminal where run_local.sh is running

## Project Structure
```bash
summarizer/
├── backend/
│   ├── app.py              # Main API (FastAPI)
│   ├── rag_engine.py       # RAG engine with ChromaDB
│   ├── requirements.txt    # Python dependencies
│   ├── Dockerfile          # For Docker
│   ├── uploads/            # Temporary PDFs (git-ignored)
│   └── chroma_data/        # Vector database (git-ignored)
├── frontend/
│   ├── src/
│   │   └── app/
│   │       ├── page.tsx    # Main interface
│   │       └── api/        # Next.js API routes
│   │           ├── upload/
│   │           │   └── route.ts
│   │           ├── summarize/
│   │           │   └── [file_id]/
│   │           │       └── route.ts
│   │           └── ask/
│   │               └── route.ts
│   ├── package.json
│   └── Dockerfile
├── ollama/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── models/             # Downloaded models (git-ignored)
├── docker-compose.yaml
├── .gitignore
├── setup_and_run.sh        # Local installation script
└── run_local.sh            # Local execution script
```
## Using the Application
#### 1. Upload a PDF

* Drag and drop a PDF file or click to select one

* The system will extract text (with OCR if needed)

* Chunks are indexed in ChromaDB for semantic search

### 2. Generate Summary

* Go to the "Summary" tab

* Click "Generate Summary"

* Wait while the system processes the document in parts

* Download the summary as TXT

### 3. Ask Questions

* Go to the "Questions" tab

* Type your question (e.g., "Who is the main character?")

* The system will find the most relevant chunks and answer

* Answers include page references

## Advanced Configuration
### Change Ollama Model

In docker-compose.yaml or backend/.env (local):
```env
OLLAMA_MODEL=llama3.2:3b  # Others: mistral, phi3, tinyllama, etc.
```
### Adjust Number of Retrieved Chunks

In backend/app.py, modify top_k:
```python
relevant_chunks = rag.find_relevant_chunks(
    top_k=15,  # Increase for more context
    ...
)
```

### Clear Database
```bash
# With Docker
docker-compose down -v
sudo rm -rf backend/chroma_data

# Local
rm -rf backend/chroma_data
```