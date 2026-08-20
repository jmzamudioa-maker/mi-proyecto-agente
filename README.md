# 🏭 Simulador Agéntico para Procesos Criogénicos

API REST construida con FastAPI e Inteligencia Artificial (Azure AI Foundry) para la orquestación y cálculo de balances de materia y energía en un tren criogénico de procesamiento de gas natural.

## 📐 Arquitectura del Sistema (Extraction-then-Execution Chain)

El proyecto utiliza un enfoque híbrido de Generación Aumentada por Recuperación (RAG) acoplado a un motor de cálculo determinista:
1. **Frontend/Cliente:** Envía los parámetros operativos (Flujo, TAGs) vía HTTP POST.
2. **Orquestador (FastAPI):** Recibe el payload y construye un "Prompt de Ingeniería" estricto.
3. **Agente IA (Azure AI Foundry):** Escanea los PFDs vectorizados, extrae termodinámica base y devuelve un JSON estructurado.
4. **Cálculo (Python):** FastAPI procesa el JSON, escala los flujos (Conservación de la Masa) y calcula balances de energía ($Q = m \cdot Cp \cdot \Delta T$).

## 🚀 Despliegue en Vercel
Este proyecto está optimizado para entornos *Serverless*. 

**Variables de Entorno Requeridas en Vercel:**
* `AZURE_TENANT_ID`: ID del inquilino de Azure.
* `AZURE_CLIENT_ID`: ID de la aplicación registrada (Service Principal).
* `AZURE_CLIENT_SECRET`: Secreto del Service Principal.
* `AZURE_AI_ENDPOINT`: Endpoint del proyecto en AI Foundry.

## 🛠️ Stack Tecnológico
* **Backend:** FastAPI (Python)
* **IA & LLM:** Azure AI Projects (GPT-4o)
* **Hosting:** Vercel (Serverless Functions)