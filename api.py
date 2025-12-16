"""
Salve este código como: api.py
Execute com: uvicorn api:app --reload
"""

import os
import re
import json
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from dotenv import load_dotenv

load_dotenv()

# Modelos Pydantic
class DocumentoRequest(BaseModel):
    texto: str


class Discrepancia(BaseModel):
    tipo: str
    gravidade: str
    artigo: str
    textoOriginal: str
    problemaEncontrado: Optional[str]
    artigoCorreto: Optional[str]
    sugestao: str


class LeiEncontrada(BaseModel):
    nome: str
    link: str
    status: str


class DocumentoResponse(BaseModel):
    textoSimplificado: str
    discrepancias: List[Dict]
    leisEncontradas: List[Dict]
    citacoesEncontradas: int


# Inicializa FastAPI
app = FastAPI(title="Analisador Jurídico API", version="1.0.0")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalisadorJuridico:
    """Analisa e simplifica documentos jurídicos com verificação de discrepâncias"""
    
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            openai_api_key=openai_api_key
        )
        self.base_url = "https://www4.planalto.gov.br/legislacao/portal-legis/legislacao-1/decretos1/2025-decretos" #"https://www4.planalto.gov.br/legislacao"
    
    def extrair_citacoes_legais(self, texto: str) -> List[Dict]:
        """Extrai todas as citações de leis e artigos do texto"""
        citacoes = []
        
        padroes = [
            r'Lei\s+n?º?\s*(\d+\.?\d*/?-?\d*)',
            r'artigo\s+(\d+[ºª]?)',
            r'art\.\s*(\d+[ºª]?)',
            r'Código\s+(Civil|Penal|de\s+Defesa\s+do\s+Consumidor)',
            r'CDC',
            r'CC',
        ]
        
        for padrao in padroes:
            matches = re.finditer(padrao, texto, re.IGNORECASE)
            for match in matches:
                citacoes.append({
                    'texto': match.group(0),
                    'posicao': match.span(),
                    'tipo': 'lei' if 'Lei' in match.group(0) else 'artigo'
                })
        
        return citacoes
    
    def buscar_conteudo_lei(self, lei_id: str) -> Optional[Dict]:
        """Busca o conteúdo completo de uma lei no portal do governo"""
        try:
            url_busca = f"{self.base_url}/legislacao-1/pesquisa"
            params = {"q": lei_id}
            
            response = requests.get(url_busca, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            primeiro_resultado = soup.find('div', class_='item')
            
            if not primeiro_resultado:
                return None
            
            link = primeiro_resultado.find('a')
            if not link:
                return None
            
            url_completa = link.get('href', '')
            if url_completa:
                conteudo_response = requests.get(url_completa, timeout=10)
                conteudo_soup = BeautifulSoup(conteudo_response.text, 'html.parser')
                conteudo = conteudo_soup.get_text()
                
                return {
                    'lei': lei_id,
                    'titulo': primeiro_resultado.find('h3').get_text(strip=True),
                    'link': url_completa,
                    'conteudo': conteudo[:5000]
                }
            
            return None
            
        except Exception as e:
            print(f"Erro ao buscar lei {lei_id}: {str(e)}")
            return None
    
    def analisar_discrepancias(self, texto: str, citacoes: List[Dict]) -> List[Dict]:
        """Analisa o texto em busca de discrepâncias nas citações legais"""
        prompt = PromptTemplate(
            input_variables=["texto", "citacoes_json", "conteudo_leis"],
            template="""Você é um especialista em direito brasileiro com acesso às leis atualizadas.

Sua tarefa é ANALISAR CRITICAMENTE as citações legais no texto e identificar:

1. ERROS GRAVES: Citações incorretas ou que tratam de assunto diferente
2. IMPRECISÕES: Citações corretas mas com interpretação inadequada
3. DESATUALIZAÇÕES: Artigos revogados ou alterados
4. CITAÇÕES CORRETAS: Validar quando estiver correto

CITAÇÕES ENCONTRADAS:
{citacoes_json}

CONTEÚDO DAS LEIS:
{conteudo_leis}

TEXTO A ANALISAR:
{texto}

INSTRUÇÕES:
- Verifique se o artigo REALMENTE trata do assunto mencionado
- Compare o que o texto DIZ com o que o artigo REALMENTE fala
- Identifique contradições entre citação e conteúdo real
- Seja RIGOROSO e PRECISO

Retorne APENAS JSON válido:
{{
  "discrepancias": [
    {{
      "tipo": "erro" | "alerta" | "ok",
      "gravidade": "alta" | "média" | "baixa",
      "artigo": "Artigo XX da Lei YYYY",
      "textoOriginal": "trecho do texto",
      "problemaEncontrado": "descrição (null se ok)",
      "artigoCorreto": "artigo correto se aplicável",
      "sugestao": "sugestão ou confirmação"
    }}
  ]
}}

JSON:"""
        )
        
        leis_identificadas = set()
        for cit in citacoes:
            if 'Lei' in cit['texto']:
                leis_identificadas.add(cit['texto'])
            elif 'CDC' in cit['texto']:
                leis_identificadas.add('Lei 8.078/90')
            elif any(x in cit['texto'] for x in ['Código Civil', 'CC']):
                leis_identificadas.add('Lei 10.406/2002')
        
        conteudo_leis = ""
        for lei in leis_identificadas:
            conteudo = self.buscar_conteudo_lei(lei)
            if conteudo:
                conteudo_leis += f"\n{'='*60}\n{lei}\n{'='*60}\n"
                conteudo_leis += conteudo['conteudo'][:2000]
        
        if not conteudo_leis:
            conteudo_leis = "Não foi possível buscar o conteúdo das leis."
        
        chain = prompt | self.llm
        
        try:
            resultado = chain.invoke({
                "texto": texto,
                "citacoes_json": json.dumps(citacoes, ensure_ascii=False, indent=2),
                "conteudo_leis": conteudo_leis
            }).content
            
            resultado = resultado.strip()
            if resultado.startswith('```'):
                resultado = '\n'.join(resultado.split('\n')[1:-1])
            
            return json.loads(resultado)['discrepancias']
            
        except Exception as e:
            print(f"Erro ao analisar: {str(e)}")
            return []
    
    def simplificar_texto(self, texto: str) -> str:
        """Simplifica o texto jurídico para linguagem coloquial"""
        prompt = PromptTemplate(
            input_variables=["texto"],
            template="""Você é um especialista em comunicação popular e direito.

Transforme o texto jurídico em linguagem SIMPLES e CLARA.

REGRAS:
1. Use palavras do dia a dia
2. Frases curtas e diretas
3. Explique termos técnicos
4. Mantenha números e prazos exatos
5. NÃO omita informações importantes
6. Se mencionar artigos, mantenha mas explique

TEXTO JURÍDICO:
{texto}

TEXTO SIMPLIFICADO:"""
        )
        
        chain = prompt | self.llm
        return chain.invoke({"texto": texto}).content.strip()
    
    def processar_documento_completo(self, texto: str) -> Dict:
        """Processa documento completo"""
        citacoes = self.extrair_citacoes_legais(texto)
        discrepancias = self.analisar_discrepancias(texto, citacoes)
        texto_simplificado = self.simplificar_texto(texto)
        
        leis_encontradas = []
        leis_unicas = set()
        
        for cit in citacoes:
            if 'Lei' in cit['texto'] or 'CDC' in cit['texto'] or 'Código' in cit['texto']:
                lei_busca = cit['texto']
                if 'CDC' in lei_busca:
                    lei_busca = 'Lei 8.078/90'
                elif 'Código Civil' in lei_busca:
                    lei_busca = 'Lei 10.406/2002'
                
                if lei_busca not in leis_unicas:
                    leis_unicas.add(lei_busca)
                    conteudo = self.buscar_conteudo_lei(lei_busca)
                    if conteudo:
                        leis_encontradas.append({
                            'nome': conteudo['titulo'],
                            'link': conteudo['link'],
                            'status': 'Vigente'
                        })
        
        return {
            'textoSimplificado': texto_simplificado,
            'discrepancias': discrepancias,
            'leisEncontradas': leis_encontradas,
            'citacoesEncontradas': len(citacoes)
        }


# Instância global do analisador
analisador = None

@app.on_event("startup")
async def startup_event():
    global analisador
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ AVISO: OPENAI_API_KEY não encontrada nas variáveis de ambiente.")
            raise ValueError("OPENAI_API_KEY não configurada")
        
        analisador = AnalisadorJuridico(api_key)
        print("✅ Analisador inicializado!")
    except Exception as e:
        print(f"⚠️ Erro ao inicializar analisador: {e}")

# @app.on_event("startup")
# async def startup_event():
#     """Inicializa o analisador na startup"""
#     global analisador
#     api_key = os.getenv('OPENAI_API_KEY')
#     if api_key:
#         analisador = AnalisadorJuridico(api_key)


@app.get("/")
async def root():
    """Endpoint raiz"""
    return {"message": "API Analisador Jurídico", "status": "online"}


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "ok"}


@app.post("/api/processar", response_model=DocumentoResponse)
async def processar_documento(documento: DocumentoRequest):
    """Endpoint para processar documento"""
    global analisador
    
    if not documento.texto:
        raise HTTPException(status_code=400, detail="Texto não fornecido")
    
    if analisador is None:
        raise HTTPException(status_code=500, detail="Analisador não inicializado. Configure OPENAI_API_KEY")
    
    try:
        resultado = analisador.processar_documento_completo(documento.texto)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))