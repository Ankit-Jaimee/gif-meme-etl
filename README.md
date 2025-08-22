# 🕷️ GIF & Meme ETL Pipeline

<div align="center">

![Python](https://img.shields.io/badge/python-v3.10.18-blue.svg)
![Scrapy](https://img.shields.io/badge/scrapy-2.13.3-green.svg)
![PostgreSQL](https://img.shields.io/badge/postgresql-14-blue.svg)
![Docker](https://img.shields.io/badge/docker-compose-blue.svg)

A robust, scalable ETL pipeline for extracting, processing, and storing GIFs and memes from various websites.
</div>

## 📝 Table of Contents
- [📦 Installation](#-installation)
- [🐳 Docker Setup](#-docker-setup)
- [🚀 Usage](#-usage)

## 📦 Installation
1. Clone the repository
```bash
git clone git@github.com:Ankit-Jaimee/gif-meme-etl.git
```
2. Create a virtual environment (Recommended python version: 3.10.18)
```bash
python -m venv venv
source venv/bin/activate
```
3. Install the dependencies
```bash
pip install -r requirements.txt
```
4. Create a `.env` file in the root directory and add the following variables:
```bash
GIPHY_API_KEY=your_giphy_api_key
```

## 🐳 Docker Setup
1. **Build the Docker image**  
   Run this command from the project root:
   ```bash
   docker compose build
   ```

2. **Create a `.env` file**  
   In the project root, add your Giphy API key:
   ```
   GIPHY_API_KEY=your_giphy_api_key
   ```

3. **Run the scraper in Docker**  
   Start the container and run the spider:
   ```bash
   docker compose up
   ```

4. **Access downloaded images**  
   Scraped images will be saved in `jaimee_scraper/images` on your host machine.

> **Note:**  
> If you change dependencies or the Dockerfile, rebuild with `docker compose build`.  
> For code changes, just restart the container.

## 🚀 Usage
### 1. Scrape GIFs from Giphy
```bash
cd jaimee_scraper
```
```bash
scrapy crawl giphy
```