import streamlit as st
import pdfplumber
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="HBL Extractor V5.0", page_icon="🔬", layout="centered")

st.title("🔬 Extractor HBLT - V5.0 (Limpio)")
st.markdown("### Resultados consolidados y sin duplicados")

# --- LISTAS CLAVE ---
ANTIBIOTICOS = [
    "Clindamicina", "Eritromicina", "Oxacilina", "Rifampicina", 
    "Trimetoprim", "Vancomicina", "Ciprofloxacino", "Gentamicina", 
    "Cefazolina", "Ampicilina", "Ceftriaxona"
]

ABREVIACIONES_ABX = {
    "Clindamicina": "Clinda", "Eritromicina": "Eritro", "Oxacilina": "Oxa",
    "Rifampicina": "Rifam", "Trimetoprim-Sulfametoxazol": "Cotrimoxazol",
    "Vancomicina": "Vanco", "Ciprofloxacino": "Cipro", "Gentamicina": "Genta"
}

def limpiar_texto(texto):
    """Limpia espacios extra y caracteres raros"""
    return re.sub(r'\s+', ' ', texto).strip()

def procesar_pdf(archivo_bytes):
    # Usamos sets (conjuntos) para evitar duplicados si hay 2 viales iguales
    datos = {
        "gram": set(),
        "germen": set(),
        "antibiograma": {}, # Diccionario para evitar repetir el mismo atb
        "otros": set()
    }
    
    with pdfplumber.open(archivo_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if not text: continue
            
            lines = text.split('\n')
            
            for line in lines:
                line = limpiar_texto(line)
                if len(line) < 3: continue
                
                # 1. FILTRO DE BASURA (Keywords a ignorar)
                ignorar = ["Tiempo de positividad", "Hospital", "Barros", "Solicitud", 
                           "Procedencia", "Validado", "Fecha", "Hora", "Página", "Rut", 
                           "Nacimiento", "Edad", "Firma", "Dra.", "T.M"]
                if any(x.upper() in line.upper() for x in ignorar): continue

                # 2. CAPTURA DE GRAM
                # Ej: "Cocaceas Gram positivo en racimo"
                if "Gram" in line and ("positivo" in line or "negativo" in line):
                    # Limpiamos el prefijo si dice "Tincion de Gram"
                    val = line.replace("Tincion de Gram", "").replace("Resultado", "").strip()
                    if len(val) > 5: # Evitar fragmentos cortos
                        datos["gram"].add(val.capitalize())

                # 3. CAPTURA DE GERMEN
                # Ej: "Staphylococcus aureus"
                if "Staphylococcus" in line or "Escherichia" in line or "Klebsiella" in line or "Enterococcus" in line or "Pseudomonas" in line:
                    # Quitamos números iniciales ej: "1 Staphylococcus..."
                    germen = re.sub(r'^\d+\s*', '', line)
                    datos["germen"].add(germen)

                # 4. CAPTURA DE ANTIBIOGRAMA (Texto plano)
                # Busca líneas que tengan un antibiótico y una R, S o I
                # Ej: "Clindamicina <=0.25 R"
                for abx in ANTIBIOTICOS:
                    if abx in line:
                        # Buscamos la letra S, R o I aislada o al final
                        match_sens = re.search(r'\b(R|S|I)\b', line)
                        if match_sens:
                            sens = match_sens.group(1)
                            nombre_corto = ABREVIACIONES_ABX.get(abx, abx)
                            datos["antibiograma"][nombre_corto] = sens # Guarda en diccionario (sobrescribe duplicados)

                # 5. CAPTURA DE ORINA / BIOQUIMICA (Solo si no es microbiología)
                if not datos["gram"] and not datos["germen"]:
                    # Regex para: NombreValor (Texto o Numero)
                    # Ej: "Glucosuria 100" o "Nitritos Negativo"
                    match = re.search(r'^([A-Za-z\s]+?)\s+(-?\d+[.,]?\d*|Negativo|Positivo|Normal|Ambar|Claro)', line, re.IGNORECASE)
                    if match:
                        nombre = match.group(1).strip()
                        valor = match.group(2).strip()
                        if len(nombre) > 3 and "Vial" not in nombre:
                            datos["otros"].add(f"{nombre} {valor}")

    # --- CONSTRUCCIÓN DEL TEXTO FINAL ---
    resultado_final = []

    # 1. Gram (Unimos con 'y' si hay diferentes, aunque raro)
    if datos["gram"]:
        resultado_final.append(f"Gram: {' y '.join(datos['gram'])}")
    
    # 2. Germen
    if datos["germen"]:
        resultado_final.append(f"Germen: {' + '.join(datos['germen'])}")

    # 3. Antibiograma (Formato: Clinda(R), Oxa(S)...)
    if datos["antibiograma"]:
        lista_abx = [f"{k}({v})" for k, v in datos["antibiograma"].items()]
        resultado_final.append(f"Sensibilidad: {', '.join(lista_abx)}")

    # 4. Otros (Orina, etc)
    if datos["otros"]:
        resultado_final.append(" // ".join(sorted(datos["otros"])))

    return " // ".join(resultado_final)

# --- INTERFAZ ---
archivo = st.file_uploader("📂 Sube PDF HBLT", type="pdf")

if archivo:
    texto = procesar_pdf(archivo)
    if texto:
        st.success("✅ Extracción limpia")
        st.code(texto, language="text")
    else:
        st.warning("⚠️ No encontré datos legibles.")
