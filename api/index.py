from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from typing import Optional
import CoolProp.CoolProp as CP
import traceback

from azure.identity import InteractiveBrowserCredential
from azure.ai.projects import AIProjectClient

app = FastAPI(title="Motor de Inferencia y Cálculo GP&I")

# --- 1. BYPASS DE CORS ABSOLUTO ---
@app.middleware("http")
async def bypass_cors_manual(request: Request, call_next):
    if request.method == "OPTIONS":
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# --- 2. INICIALIZACIÓN DEL AGENTE AZURE (RAG) ---
print("--- Iniciando Canal de Comunicación GP&I ---")
endpoint = "https://rg-agente-planta-gas-resource.services.ai.azure.com/api/projects/rg-agente-planta-gas"
my_agent = "Agente-Experto-Planta-Gas"
my_version = "1"

try:
    print("[*] Autenticando sesión en Azure...")
    credential = InteractiveBrowserCredential(tenant_id="7cb2c112-23ee-4730-b741-cf995311a163")
    project_client = AIProjectClient(endpoint=endpoint, credential=credential)
    openai_client = project_client.get_openai_client()
    print("[*] Conexión a Azure exitosa.")
except Exception as e:
    print(f"[ERROR DE AUTENTICACIÓN]: {e}")

# --- 3. MODELOS DE ESTRUCTURA JSON ---
class MensajeChat(BaseModel):
    pregunta: str

class CondicionesEntrada(BaseModel):
    temp_c: float
    pres_barg: float

class DatosEquipo(BaseModel):
    pres_out_barg: Optional[float] = None
    eficiencia: Optional[float] = None

class PayloadCalculo(BaseModel):
    tipo_evaluacion: str
    mezcla: str
    flujo_kg_h: float
    entrada: CondicionesEntrada
    equipo: Optional[DatosEquipo] = None

# --- 4. RUTAS DEL SERVIDOR ---

@app.post("/api/chat")
async def consultar_manuales(mensaje: MensajeChat):
    """Fase 1: El Asesor IA lee manuales y propone un plan."""
    try:
        response = openai_client.responses.create(
            input=[{"role": "user", "content": mensaje.pregunta}],
            extra_body={
                "agent_reference": {
                    "name": my_agent, 
                    "version": my_version, 
                    "type": "agent_reference"
                }
            }
        )
        return {"status": "success", "respuesta": response.output_text}
    except Exception as e:
        return {"status": "error", "detalle": str(e)}

@app.post("/api/calcular")
async def ejecutar_evaluacion(payload: PayloadCalculo):
    """Fase 2: Motor termodinámico estructurado (CoolProp)."""
    try:
        # Conversiones base a unidades SI
        t_in_k = payload.entrada.temp_c + 273.15
        p_in_pa = (payload.entrada.pres_barg + 1.01325) * 100000
        fluido = f"PR::{payload.mezcla}"

        # MÓDULO 1: Flash Básico
        if payload.tipo_evaluacion == "flash":
            h_in_j_kg = CP.PropsSI('H', 'T', t_in_k, 'P', p_in_pa, fluido)
            d_in_kg_m3 = CP.PropsSI('D', 'T', t_in_k, 'P', p_in_pa, fluido)
            
            return {
                "status": "success",
                "tipo": "flash",
                "resultados": {
                    "entalpia": round(h_in_j_kg / 1000, 2),
                    "densidad": round(d_in_kg_m3, 2)
                }
            }

        # MÓDULO 2: Expansor / Compresor
        elif payload.tipo_evaluacion == "expander":
            p_out_pa = (payload.equipo.pres_out_barg + 1.01325) * 100000
            eficiencia = payload.equipo.eficiencia

            # Estado 1 (Entrada)
            h_in = CP.PropsSI('H', 'T', t_in_k, 'P', p_in_pa, fluido)
            s_in = CP.PropsSI('S', 'T', t_in_k, 'P', p_in_pa, fluido)

            # Estado 2 Isentrópico (Ideal)
            h_out_ideal = CP.PropsSI('H', 'S', s_in, 'P', p_out_pa, fluido)

            # Estado 2 Real (Aplicando eficiencia)
            h_out_real = h_in - eficiencia * (h_in - h_out_ideal)

            # Cálculos de resultados
            delta_p = payload.entrada.pres_barg - payload.equipo.pres_out_barg
            delta_h_kj = (h_out_real - h_in) / 1000
            potencia_kw = abs(delta_h_kj) * (payload.flujo_kg_h / 3600)

            return {
                "status": "success",
                "tipo": "expander",
                "resultados": {
                    "delta_p": round(delta_p, 2),
                    "delta_h": round(delta_h_kj, 2),
                    "potencia": round(potencia_kw, 2)
                }
            }
        
        else:
            return {"status": "error", "detalle": "Módulo de evaluación no reconocido."}

    except Exception as e:
        return {"status": "error", "detalle": traceback.format_exc()}