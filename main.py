import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import openai
import os
import json
import pandas as pd
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# Cargar clave API desde el entorno
load_dotenv()
#openai.api_key = os.getenv("OPENAI_API_KEY")
openai.api_key = ""

# 1. Extraer el Árbol del Sitio Web
def extract_site_tree(base_url, max_depth=2):
    """
    Recorre el sitio web para construir el árbol de páginas.
    """
    queue = [(base_url, 0)]
    visited = set()
    site_tree = {}

    while queue:
        url, depth = queue.pop(0)
        if depth > max_depth or url in visited:
            continue
        visited.add(url)

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            links = [
                urljoin(base_url, a["href"])
                for a in soup.find_all("a", href=True)
                if urlparse(urljoin(base_url, a["href"])).netloc == urlparse(base_url).netloc
            ]
            site_tree[url] = list(set(links))
            queue.extend((link, depth + 1) for link in links)
        except Exception as e:
            site_tree[url] = {"error": str(e)}

    return site_tree

# 2. Mostrar el Árbol del Sitio en Formato Jerárquico
def print_site_tree(site_tree, base_url, depth=0, visited=None):
    """
    Muestra el árbol del sitio en formato jerárquico con indentación.
    Evita recursión infinita controlando los nodos visitados.
    """
    if visited is None:
        visited = set()

    if base_url in visited:
        return
    visited.add(base_url)

    indent = "  " * depth
    print(f"{indent}└── {base_url}")

    children = site_tree.get(base_url, [])
    if isinstance(children, list):
        for child in children:
            print_site_tree(site_tree, child, depth + 1, visited)

# 3. Exportar el Árbol del Sitio como JSON
def export_site_tree_as_json(site_tree, base_url):
    """
    Exporta el árbol del sitio como un JSON jerárquico.
    Evita recursión infinita controlando los nodos visitados.
    """
    visited = set()

    def build_tree(url):
        if url in visited:
            return {}
        visited.add(url)

        children = site_tree.get(url, [])
        if isinstance(children, list):
            return {"children": {child: build_tree(child) for child in children}}
        return {}

    return {base_url: build_tree(base_url)}

# 4. Extraer Información HTML
def extract_page_info(url):
    """
    Extrae etiquetas HTML relevantes y meta información.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extraer etiquetas
        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]
        h3_tags = [h3.get_text(strip=True) for h3 in soup.find_all("h3")]
        span_tags = [span.get_text(strip=True) for span in soup.find_all("span")]
        p_tags = [p.get_text(strip=True) for p in soup.find_all("p")]
        label_tags = [label.get_text(strip=True) for label in soup.find_all("label")]
        meta_tags = {
            meta.get("name", meta.get("property", "unknown")): meta.get("content", "unknown")
            for meta in soup.find_all("meta")
        }

        return {
            "url": url,
            "h1": h1_tags,
            "h2": h2_tags,
            "h3": h3_tags,
            "span": span_tags,
            "p": p_tags,
            "label": label_tags,
            "meta": meta_tags,
        }
    except Exception as e:
        return {"url": url, "error": str(e)}

# 5. Verificar URLs con solicitudes paralelas
def verify_urls_with_table(site_tree):
    """
    Verifica si las URLs del árbol están funcionando correctamente y genera una tabla.
    """
    def check_url(url):
        try:
            response = requests.head(url, timeout=10)
            return {"URL": url, "Estado": response.status_code}
        except Exception as e:
            return {"URL": url, "Estado": f"Error: {str(e)}"}

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(check_url, site_tree.keys()))

    return pd.DataFrame(results)

# 6. Mostrar etiquetas en tablas
def display_html_tables(page_info):
    """
    Genera tablas separadas para etiquetas meta y otras etiquetas HTML.
    """
    # Crear DataFrame para etiquetas meta
    meta_data = []
    for page, info in page_info.items():
        if "meta" in info:
            for key, value in info["meta"].items():
                meta_data.append({"Página": page, "Etiqueta": key, "Contenido": value})

    meta_df = pd.DataFrame(meta_data)

    # Crear DataFrame para otras etiquetas
    html_data = []
    for page, info in page_info.items():
        for tag in ["h1", "h2", "h3", "span", "p", "label"]:
            for content in info.get(tag, []):
                html_data.append({"Página": page, "Etiqueta": tag, "Contenido": content})

    html_df = pd.DataFrame(html_data)

    return meta_df, html_df

# 7 Analizar Imágenes
def analyze_images(url):
    """
    Analiza las imágenes en la página para verificar tamaños y dimensiones.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        images = []

        for img in soup.find_all("img", src=True):
            img_url = urljoin(url, img["src"])
            try:
                img_response = requests.head(img_url, timeout=10)
                img_size = int(img_response.headers.get("Content-Length", 0)) / 1024  # Convertir a KB
                images.append({"url": img_url, "size_kb": round(img_size, 2)})
            except Exception as e:
                images.append({"url": img_url, "error": str(e)})

        return images
    except Exception as e:
        return {"url": url, "error": str(e)}

# 8. Enviar Datos a GPT
def send_to_gpt(site_tree, page_info, image_analysis):
    """
    Envía los datos recolectados a GPT para obtener recomendaciones.
    """
    def summarize_data(data, limit=1000):
        return str(data)[:limit] + "..." if len(str(data)) > limit else str(data)

    prompt = f"""
    Analiza la estructura del sitio web y proporciona recomendaciones de SEO:
    Árbol del sitio: {summarize_data(site_tree)}
    Información de las páginas: {summarize_data(page_info)}
    Análisis de imágenes: {summarize_data(image_analysis)}
    Además, analiza las etiquetas HTML y proporciona sugerencias para optimizar su contenido:
    {summarize_data(page_info)}
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error al enviar datos a GPT: {e}"

# 9. Función Principal
def main():
    url = "https://dibeal.com/"
    print("Extrayendo el árbol del sitio...")
    site_tree = extract_site_tree(url)

    print("\nÁrbol del sitio estructurado:")
    print_site_tree(site_tree, url)

    print("\nExportando el árbol del sitio como JSON...")
    tree_json = export_site_tree_as_json(site_tree, url)

    with open("site_tree.json", "w") as json_file:
        json.dump(tree_json, json_file, indent=4)

    print("Árbol del sitio guardado como 'site_tree.json'")

    print("\nExtrayendo información de las páginas...")
    page_info = {page: extract_page_info(page) for page in site_tree}

    print("\nVerificando URLs y generando tabla...")
    url_status_table = verify_urls_with_table(site_tree)
    print("\nEstado de URLs del Árbol del Sitio:")
    print(url_status_table)

    print("\nGenerando tablas para etiquetas meta y HTML...")
    meta_df, html_df = display_html_tables(page_info)
    print("\nEtiquetas Meta:")
    print(meta_df)
    print("\nEtiquetas HTML:")
    print(html_df)

    print("\nAnalizando imágenes...")
    image_analysis = {page: analyze_images(page) for page in site_tree}

    print("\nGenerando recomendaciones con GPT...")
    gpt_recommendations = send_to_gpt(site_tree, page_info, image_analysis)
    print("\nRecomendaciones:")
    print(gpt_recommendations)

if __name__ == "__main__":
    main()
