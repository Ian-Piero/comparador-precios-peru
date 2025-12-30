import streamlit as st
import subprocess
import sys
import os
import json
from groq import Groq

# ================= CONFIG =================
API_KEY_DIRECTA = "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"

st.set_page_config(
    page_title="Comparador Tech Perú",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ Comparador de productos tecnológicos")
st.markdown("Comparando precios en **Mercado Libre, Coolbox y Hiraoka**")

# ============== SCRAPER ===================
def buscar_y_extraer(producto):
    script_temp = "scraper_temp.py"

    codigo = f'''
import asyncio
from playwright.async_api import async_playwright

async def extraer_tienda(context, url, tienda, selector):
    page = await context.new_page()
    resultados = []

    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)

        # Scroll para cargar productos
        for _ in range(3):
            await page.mouse.wheel(0, 3000)
            await page.wait_for_timeout(1200)

        try:
            await page.wait_for_selector(selector, timeout=20000)
        except:
            print(f"NO_DATA::{{tienda}}")
            return []

        items = await page.query_selector_all(selector)
        print(f"{{tienda}}: {{len(items)}} productos")

        for item in items[:6]:
            try:
                texto = await item.inner_text()
                texto = texto.replace("\\n", " ").strip()

                link_elem = await item.query_selector("a")
                link = await link_elem.get_attribute("href") if link_elem else ""

                if link.startswith("/"):
                    if "mercadolibre" in url:
                        link = "https://www.mercadolibre.com.pe" + link
                    elif "coolbox" in url:
                        link = "https://www.coolbox.pe" + link
                    elif "hiraoka" in url:
                        link = "https://hiraoka.com.pe" + link

                if len(texto) > 60:
                    resultados.append(
                        f"TIENDA:{{tienda}}|DATA:{{texto[:500]}}|LINK:{{link}}"
                    )
            except:
                continue

    except Exception as e:
        print(f"ERROR::{{tienda}}::{{e}}")
    finally:
        await page.close()

    return resultados


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        q = "{producto}".replace(" ", "+")

        tareas = [
            # Mercado Libre
            extraer_tienda(
                context,
                f"https://listado.mercadolibre.com.pe/{{q.replace('+','-')}}",
                "Mercado Libre",
                ".ui-search-result"
            ),

            # Coolbox
            extraer_tienda(
                context,
                f"https://www.coolbox.pe/{{q}}?_q={{q}}&map=ft",
                "Coolbox",
                "section.vtex-product-summary-2-x-container"
            ),

            # Hiraoka
            extraer_tienda(
                context,
                f"https://hiraoka.com.pe/catalogsearch/result/?q={{q}}",
                "Hiraoka",
                ".product-item-info"
            )
        ]

        listas = await asyncio.gather(*tareas)
        total = [i for sub in listas for i in sub]

        if total:
            print("###".join(total))

        await browser.close()

asyncio.run(run())
'''
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(codigo)

    try:
        salida = subprocess.check_output(
            [sys.executable, script_temp],
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return salida.split("###") if salida.strip() else []
    finally:
        if os.path.exists(script_temp):
            os.remove(script_temp)


# ============== IA ===================
def comparar_con_ia(datos, api_key):
    client = Groq(api_key=api_key)

    prompt = f"""
Eres un experto en compras en Perú.
Devuelve SOLO un JSON con esta estructura:

{{
  "productos": [
    {{
      "tienda": "",
      "nombre": "",
      "precio": 0,
      "enlace": ""
    }}
  ]
}}

Extrae productos REALES.
Si no hay precio, omite el producto.
Datos:
{chr(10).join(datos)}
"""

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{{"role": "user", "content": prompt}}],
        response_format={{"type": "json_object"}}
    )

    return completion.choices[0].message.content


# ============== UI ===================
producto = st.text_input(
    "🔎 Producto a buscar",
    placeholder="Ej: iPhone 15, Laptop Gamer, TV Samsung..."
)

if st.button("Buscar"):
    if not producto:
        st.warning("Ingresa un producto")
    else:
        try:
            with st.spinner("Buscando en tiendas..."):
                resultados = buscar_y_extraer(producto)

            if not resultados:
                st.error("No se encontraron resultados.")
            else:
                with st.spinner("Procesando con IA..."):
                    respuesta = comparar_con_ia(resultados, API_KEY_DIRECTA)
                    data = json.loads(respuesta)
                    productos = data.get("productos", [])

                st.subheader("📊 Comparación de precios")
                st.dataframe(
                    productos,
                    column_config={{
                        "enlace": st.column_config.LinkColumn("Link"),
                        "precio": st.column_config.NumberColumn(
                            "Precio (S/.)", format="S/. %d"
                        ),
                        "nombre": st.column_config.TextColumn(
                            "Producto", width="large"
                        )
                    }},
                    hide_index=True,
                    width="stretch"
                )

        except Exception as e:
            st.error(f"Error: {{e}}")
