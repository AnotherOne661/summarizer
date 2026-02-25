#!/bin/bash

echo "========================================="
echo "🚀 Configuración del Resumidor de PDF con IA"
echo "========================================="
echo ""

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_step() {
    echo -e "${BLUE}➡️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Verificar si se ejecuta como root (no recomendado)
if [ "$EUID" -eq 0 ]; then 
   print_warning "No ejecutes este script como root"
   exit 1
fi

# =========================================
# PASO 1: Verificar sistema operativo
# =========================================
print_step "Verificando sistema operativo..."

OS="unknown"
if [ -f /etc/debian_version ]; then
    OS="debian"
    print_success "Sistema Debian/Ubuntu detectado"
elif [ -f /etc/redhat-release ]; then
    OS="redhat"
    print_success "Sistema RedHat/CentOS detectado"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    print_success "macOS detectado"
else
    print_error "Sistema operativo no soportado"
    exit 1
fi

# =========================================
# PASO 2: Instalar dependencias del sistema
# =========================================
print_step "Instalando dependencias del sistema..."

if [ "$OS" = "debian" ]; then
    sudo apt update
    sudo apt install -y \
        python3-pip \
        python3-venv \
        tesseract-ocr \
        tesseract-ocr-spa \
        tesseract-ocr-eng \
        poppler-utils \
        wget \
        curl \
        git
elif [ "$OS" = "redhat" ]; then
    sudo yum install -y \
        python3-pip \
        tesseract \
        tesseract-langpack-spa \
        tesseract-langpack-eng \
        poppler-utils \
        wget \
        curl \
        git
elif [ "$OS" = "macos" ]; then
    # Verificar si homebrew está instalado
    if ! command -v brew &> /dev/null; then
        print_step "Instalando Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install \
        tesseract \
        tesseract-lang \
        poppler \
        wget \
        curl \
        git
fi

print_success "Dependencias del sistema instaladas"

# =========================================
# PASO 3: Instalar Ollama
# =========================================
print_step "Instalando Ollama..."

if ! command -v ollama &> /dev/null; then
    if [ "$OS" = "debian" ] || [ "$OS" = "redhat" ]; then
        curl -fsSL https://ollama.com/install.sh | sh
    elif [ "$OS" = "macos" ]; then
        brew install ollama
    fi
    print_success "Ollama instalado"
else
    print_success "Ollama ya está instalado"
fi

# =========================================
# PASO 4: Descargar modelo de Ollama
# =========================================
print_step "Descargando modelo llama3.2:3b (esto puede tomar varios minutos)..."

# Asegurar que Ollama está corriendo
if [ "$OS" != "macos" ]; then
    sudo systemctl start ollama
fi

# Descargar modelo
ollama pull llama3.2:3b
print_success "Modelo descargado"

# =========================================
# PASO 5: Configurar entorno virtual de Python
# =========================================
print_step "Configurando entorno virtual de Python..."

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_success "Entorno virtual creado"
fi

# Activar entorno virtual e instalar dependencias
source venv/bin/activate

# Instalar dependencias Python
print_step "Instalando dependencias de Python..."
pip install --upgrade pip
pip install -r backend/requirements.txt

print_success "Dependencias de Python instaladas"

# =========================================
# PASO 6: Configurar frontend (Node.js y dependencias)
# =========================================
print_step "Configurando frontend..."

# Verificar si Node.js está instalado y es versión 20+
if ! command -v node &> /dev/null; then
    print_step "Instalando Node.js 20..."
    if [ "$OS" = "debian" ]; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt install -y nodejs
    elif [ "$OS" = "redhat" ]; then
        curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
        sudo yum install -y nodejs
    elif [ "$OS" = "macos" ]; then
        brew install node@20
    fi
else
    NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
    if [ "$NODE_VERSION" -lt 20 ]; then
        print_warning "Node.js versión $NODE_VERSION detectada. Se requiere versión 20+"
        print_step "Actualizando a Node.js 20..."
        if [ "$OS" = "debian" ]; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt install -y nodejs
        elif [ "$OS" = "redhat" ]; then
            curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
            sudo yum install -y nodejs
        elif [ "$OS" = "macos" ]; then
            brew upgrade node@20
        fi
    fi
fi

print_success "Node.js $(node -v) instalado"

# Instalar dependencias del frontend
print_step "Instalando dependencias del frontend (npm install)..."
cd frontend
npm install
if [ $? -ne 0 ]; then
    print_error "Error al instalar dependencias del frontend"
    exit 1
fi
cd ..
print_success "Dependencias del frontend instaladas"

# =========================================
# PASO 7: Crear archivos de configuración y carpetas necesarias
# =========================================
print_step "Creando archivos de configuración y carpetas..."

# Backend .env para entorno local (con ruta relativa)
cat > backend/.env << EOF
UPLOAD_FOLDER=./uploads
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
EOF

# Frontend .env.local
cat > frontend/.env.local << EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF

# Crear carpetas necesarias
mkdir -p backend/uploads
mkdir -p backend/chroma_data
chmod 755 backend/uploads backend/chroma_data 2>/dev/null

print_success "Archivos de configuración y carpetas creados"

# =========================================
# PASO 8: Crear script de ejecución (run_local.sh)
# =========================================
print_step "Creando script de ejecución..."

cat > run_local.sh << 'EOF'
#!/bin/bash

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=========================================${NC}"
echo -e "${GREEN}🚀 Iniciando Resumidor de PDF con IA${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Verificar que el frontend tiene dependencias instaladas
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${RED}❌ Error: frontend/node_modules no encontrado. Ejecuta primero ./setup_and_run.sh${NC}"
    exit 1
fi

# Cargar variables de entorno del backend
if [ -f backend/.env ]; then
    echo -e "${BLUE}📦 Cargando configuración desde backend/.env${NC}"
    export $(grep -v '^#' backend/.env | xargs)
else
    echo -e "${YELLOW}⚠️  No se encontró backend/.env, usando valores por defecto${NC}"
    export UPLOAD_FOLDER="./uploads"
    export OLLAMA_URL="http://localhost:11434"
    export OLLAMA_MODEL="llama3.2:3b"
fi

# Crear carpeta de uploads si no existe
mkdir -p "$UPLOAD_FOLDER"
chmod 755 "$UPLOAD_FOLDER" 2>/dev/null

# Función para matar procesos al salir
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Deteniendo servicios...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Activar entorno virtual
source venv/bin/activate

# Iniciar backend
echo -e "${BLUE}📦 Iniciando backend en http://localhost:8000${NC}"
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Esperar a que el backend esté listo
sleep 3

# Iniciar frontend
echo -e "${BLUE}🎨 Iniciando frontend en http://localhost:3000${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo -e "${GREEN}✅ Servicios iniciados correctamente${NC}"
echo -e "📊 Backend:  http://localhost:8000"
echo -e "🌐 Frontend: http://localhost:3000"
echo -e "📚 API Docs: http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Presiona Ctrl+C para detener todos los servicios${NC}"
echo ""

# Esperar a que los procesos terminen
wait $BACKEND_PID $FRONTEND_PID
EOF

chmod +x run_local.sh

print_success "Script de ejecución creado"

# =========================================
# PASO 9: Resumen final
# =========================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✅ CONFIGURACIÓN COMPLETADA CON ÉXITO${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "📋 Para ejecutar la aplicación:"
echo "   ./run_local.sh"
echo ""
echo "🔗 Accesos:"
echo "   Backend API:  http://localhost:8000"
echo "   Frontend:     http://localhost:3000"
echo ""
echo "📁 Estructura:"
echo "   - backend/uploads/: Archivos PDF temporales"
echo "   - backend/chroma_data/: Base de datos vectorial"
echo "   - frontend/: Aplicación Next.js"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   1. Asegúrate de que los puertos 8000 y 3000 estén libres"
echo "   2. Para detener: Ctrl+C en la terminal donde corra run_local.sh"
echo "   3. Los PDFs subidos se guardan en backend/uploads/"
echo ""

# Hacer ejecutable el script principal (por si acaso)
chmod +x setup_and_run.sh