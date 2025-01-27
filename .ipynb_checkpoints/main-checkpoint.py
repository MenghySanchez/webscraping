import cloudscraper
import certifi
import ssl
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import networkx as nx
import matplotlib.pyplot as plt


# Función para hacer scraping con cloudscraper
def scrape_with_cloudscraper(url):
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        scraper = cloudscraper.create_scraper(ssl_context=ssl_context)
        response = scraper.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        titles = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]

        return {"titles": titles, "paragraphs": paragraphs, "url": url, "html": soup}
    except Exception as e:
        return {"error": str(e)}


# Función para extraer el árbol del sitio
def extract_site_tree(base_url, max_depth=2):
    visited = set()
    site_tree = {}

    def crawl(url, depth):
        if depth > max_depth or url in visited:
            return
        visited.add(url)
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            links = [
                urljoin(base_url, a["href"])
                for a in soup.find_all("a", href=True)
                if urlparse(urljoin(base_url, a["href"])).netloc
                == urlparse(base_url).netloc
            ]
            site_tree[url] = list(set(links))  # Eliminar duplicados
            for link in links:
                crawl(link, depth + 1)
        except Exception as e:
            site_tree[url] = {"error": str(e)}

    crawl(base_url, 0)
    return site_tree


# Clasificar las páginas según su tipo
def classify_page(url, base_url):
    if url == base_url:
        return "principal"
    elif any(category in url.lower() for category in ["productos", "categorias", "servicios"]):
        return "categoría"
    elif any(landing in url.lower() for landing in ["contacto", "privacidad", "politicas", "terminos"]):
        return "aterrizaje"
    else:
        return "otro"


# Dibujar el árbol del sitio
def plot_site_tree(site_tree, base_url):
    graph = nx.DiGraph()
    node_colors = {}

    for parent, children in site_tree.items():
        if isinstance(children, list):
            for child in children:
                graph.add_edge(parent, child)
                page_type = classify_page(child, base_url)
                node_colors[child] = (
                    "gold" if page_type == "principal"
                    else "skyblue" if page_type == "categoría"
                    else "lightgreen" if page_type == "aterrizaje"
                    else "gray"
                )
        if parent not in node_colors:
            node_colors[parent] = "gold" if parent == base_url else "gray"

    color_list = [node_colors[node] for node in graph.nodes]
    plt.figure(figsize=(15, 10))
    pos = nx.spring_layout(graph, k=0.5, seed=42)
    nx.draw(
        graph, pos, with_labels=True, node_size=1000, node_color=color_list,
        font_size=8, font_weight="bold", edge_color="gray"
    )
    plt.title("Árbol del Sitio Web", fontsize=14)
    plt.show()


# Analizar contenido SEO
def analyze_content(data):
    if "error" in data:
        return {"error": f"No se pudo analizar la página: {data['error']}"}

    recommendations = []
    for title in data["titles"]:
        if len(title) > 60:
            recommendations.append(f"El título '{title}' es demasiado largo.")
        if len(title) < 30:
            recommendations.append(f"El título '{title}' es demasiado corto.")

    for paragraph in data["paragraphs"]:
        word_count = len(paragraph.split())
        if word_count > 150:
            recommendations.append(f"Párrafo demasiado largo: '{paragraph[:100]}...'")
        if word_count < 50:
            recommendations.append(f"Párrafo demasiado corto: '{paragraph}'")

    return recommendations


# Analizar imágenes
def analyze_images(images, base_url):
    total_size = 0
    image_details = []
    for img in images:
        img_url = urljoin(base_url, img.get("src", ""))
        try:
            response = requests.get(img_url, stream=True)
            response.raise_for_status()
            img_size = int(response.headers.get("Content-Length", 0))
            total_size += img_size
            image_details.append({
                "url": img_url,
                "size_kb": round(img_size / 1024, 2),
                "width": img.get("width", "desconocido"),
                "height": img.get("height", "desconocido"),
            })
        except Exception:
            image_details.append({"url": img_url, "error": "No se pudo analizar"})

    return {"total_size_kb": round(total_size / 1024, 2), "image_details": image_details}


# Función principal
def main():
    url = "https://tbo.com.ec"
    print("Scraping de la página principal...")
    scraped_data = scrape_with_cloudscraper(url)

    if "error" in scraped_data:
        print(scraped_data["error"])
        return

    recommendations = analyze_content(scraped_data)
    print("\nRecomendaciones SEO:")
    for rec in recommendations:
        print(f"- {rec}")

    print("\nAnálisis de imágenes:")
    soup = scraped_data["html"]
    image_analysis = analyze_images(soup.find_all("img"), url)
    for img in image_analysis["image_details"]:
        print(f"- URL: {img['url']}, Tamaño: {img.get('size_kb', 'desconocido')} KB, Dimensiones: {img.get('width', 'desconocido')}x{img.get('height', 'desconocido')}")

    print("\nExtrayendo el árbol del sitio...")
    site_tree = extract_site_tree(url, max_depth=2)

    print("\nÁrbol del sitio (texto):")
    for page, links in site_tree.items():
        print(f"{page}:\n  {', '.join(links[:5])}...\n")

    print("\nMostrando el árbol del sitio como gráfico...")
    plot_site_tree(site_tree, url)


if __name__ == "__main__":
    main()