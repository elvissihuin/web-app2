# Usar una imagen oficial de Python ligera
FROM python:3.11-slim

# Instalar FFmpeg (Requisito fundamental para yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar el archivo de dependencias primero (aprovechar caché de Docker)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código del proyecto
COPY . .

# Exponer el puerto (Render lo inyectará dinámicamente)
EXPOSE 5000

# Comando para ejecutar la aplicación en producción con Gunicorn
# Importante: Como usamos SSE (Server-Sent Events) para la barra de progreso, 
# necesitamos un worker asíncrono como gthread o gevent. 
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "0", "app:app"]
