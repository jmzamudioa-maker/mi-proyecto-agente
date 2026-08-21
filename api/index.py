from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import re
import traceback  # <--- NUEVA LIBRERÍA DE DIAGNÓSTICO

from azure.identity import ClientSecretCredential
from azure.ai.projects import AIProjectClient

app = FastAPI(title="API Agente Simulador - Planta de Gas")

class EscenarioRequest(BaseModel):
    flujo_mmscfd: float
    tag_caja: str
    tag_exp: str

def calcular_energia(flujo_base_lb_hr, factor_escala, t_in_f, t_out_f, cp_asumido=0.6):
    try:
        flujo_escalado = flujo_base_lb_hr * factor_escala
        delta_t = abs(t_in_f - t_out_f)
        duty_btu_hr = flujo_escalado * cp_asumido * delta_t
        return flujo_escalado, duty_btu_hr
    except:
        return None, None

@app.post("/api/simular")
def ejecutar_simulacion(escenario: EscenarioRequest):
    try:
        tenant = os.environ.get("AZURE_TENANT_ID", "").strip()
        client = os.environ.get("AZURE_CLIENT_ID", "").strip()
        secret = os.environ.get("AZURE_CLIENT_SECRET", "").strip()
        endpoint = os.environ.get("AZURE_AI_ENDPOINT", "").strip()
        
        if not all([tenant, client, secret, endpoint]):
            raise ValueError("Faltan variables de entorno en Vercel.")

        credential = ClientSecretCredential(
            tenant_id=tenant,
            client_id=client,
            client_secret=secret
        )
        
        project_client = AIProjectClient(endpoint=endpoint, credential=credential)
        
        with project_client:
            openai_client = project_client.get_openai_client()
            my_agent = "Agente-Experto-Planta-Gas"
            my_version = "1"
            
            factor_escala = escenario.flujo_mmscfd / 216.7
            
            prompt_calculo = rf"""
            Actúa como un extractor de datos para un simulador riguroso.
            REGLA ABSOLUTA: Tu respuesta debe ser ÚNICAMENTE un objeto JSON. Cero texto. Sin bloques markdown.
            
            Extrae de los documentos del PFD:
            1. Balance de Materia (Corr 4, 5 y 6). Corriente 4 = Corriente 5 + Corriente 6.
            2. Recuperación C3: (C3 en Corr 6 / C3 en Corr 4) * 100.
            3. Caja Fría ({escenario.tag_caja}): Temp entrada/salida y flujo másico base.
            4. Turboexpander ({escenario.tag_exp}): Presión/Temp entrada/salida, y flujo másico base.

            ESTRUCTURA JSON EXACTA OBLIGATORIA:
            {{
                "recuperacion_c3_porcentaje": <numero>,
                "caja_fria": {{"t_in_f": <numero>, "t_out_f": <numero>, "flujo_base_lb_hr": <numero>}},
                "expander": {{"p_in_psi": <numero>, "t_in_f": <numero>, "p_out_psi": <numero>, "t_out_f": <numero>, "flujo_base_lb_hr": <numero>}}
            }}
            """
            
            response = openai_client.responses.create(
                input=[{"role": "user", "content": prompt_calculo}],
                extra_body={"agent_reference": {"name": my_agent, "version": my_version, "type": "agent_reference"}}
            )

            json_limpio = re.sub(r'```json\n|```', '', response.output_text).strip()
            datos_ia = json.loads(json_limpio)
            
            caja = datos_ia.get('caja_fria', {})
            _, duty_caja = calcular_energia(float(caja.get('flujo_base_lb_hr') or 150000), factor_escala, float(caja.get('t_in_f') or 0), float(caja.get('t_out_f') or 0))
            
            exp = datos_ia.get('expander', {})
            _, work_exp = calcular_energia(float(exp.get('flujo_base_lb_hr') or 150000), factor_escala, float(exp.get('t_in_f') or 0), float(exp.get('t_out_f') or 0))
            hp_exp = work_exp / 2544.43 if work_exp else 0
            
            return {
                "status": "success",
                "parametros_entrada": escenario.model_dump(),
                "resultados": {
                    "factor_escala": round(factor_escala, 4),
                    "recuperacion_c3_porcentaje": datos_ia.get('recuperacion_c3_porcentaje'),
                    "caja_fria_duty_mmbtu_hr": round(duty_caja / 1e6, 2) if duty_caja else None,
                    "turboexpander_potencia_hp": round(hp_exp, 1) if hp_exp else None
                }
            }
# Despertando el webhook desde la nube
    except Exception as e:
        # AQUÍ ESTÁ LA MAGIA: Esto extraerá la raíz profunda del error de red
        error_details = traceback.format_exc()
# Reactivando el webhook de Vercel
        raise HTTPException(status_code=500, detail=f"REPORTE TÉCNICO:\n{error_details}")
