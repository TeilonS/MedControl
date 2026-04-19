# Imagem base leve com Python 3.11
FROM python:3.11-slim-bullseye

# Previne que o Python gere arquivos .pyc e permite logs em tempo real
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para psycopg2 e outras libs
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Expõe a porta padrão do Flask
EXPOSE 5000

# Comando para rodar a aplicação com Gunicorn (padrão de produção)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
