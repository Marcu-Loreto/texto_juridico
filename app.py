
import streamlit as st
import requests
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Configuração de Logging
if 'logger_initialized' not in st.session_state:
    logger = logging.getLogger('SimplificadorJuridico')
    logger.setLevel(logging.INFO)
    
    # Handler para arquivo com rotação (máx 5MB, mantém 3 backups)
    file_handler = RotatingFileHandler(
        'app_juridico.log',
        maxBytes=5*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    
    # Formato dos logs
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    st.session_state.logger_initialized = True
    st.session_state.logger = logger
    
    logger.info('='*60)
    logger.info('Aplicação Simplificador Jurídico iniciada')
    logger.info('='*60)
else:
    logger = st.session_state.logger

# Configuração da página
st.set_page_config(
    page_title="Simplificador Jurídico",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }
    .success-box {
        padding: 1rem;
        background-color: #ecfdf5;
        border-left: 4px solid #10b981;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .error-box {
        padding: 1rem;
        background-color: #fef2f2;
        border-left: 4px solid #ef4444;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fffbeb;
        border-left: 4px solid #f59e0b;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stButton>button {
        width: 100%;
        background-color: #4f46e5;
        color: white;
        font-weight: bold;
        padding: 0.75rem;
        border-radius: 0.5rem;
    }
    .stButton>button:hover {
        background-color: #4338ca;
    }
</style>
""", unsafe_allow_html=True)


def processar_documento_api(texto: str, api_url: str = "http://localhost:8000"):
    """Chama a API FastAPI para processar o documento"""
    logger = st.session_state.get('logger', logging.getLogger('SimplificadorJuridico'))
    
    try:
        logger.info(f"Iniciando processamento de documento (tamanho: {len(texto)} caracteres)")
        logger.debug(f"URL da API: {api_url}")
        
        response = requests.post(
            f"{api_url}/api/processar",
            json={"texto": texto},
            timeout=60
        )
        response.raise_for_status()
        
        resultado = response.json()
        logger.info(f"Documento processado com sucesso - {resultado.get('citacoesEncontradas', 0)} citações encontradas")
        logger.info(f"Discrepâncias encontradas: {len(resultado.get('discrepancias', []))}")
        
        return resultado, None
    except requests.exceptions.Timeout:
        erro = "Timeout ao processar documento - A API demorou muito para responder"
        logger.error(erro)
        return None, erro
    except requests.exceptions.ConnectionError as e:
        erro = f"Erro de conexão com a API: {str(e)}"
        logger.error(erro)
        return None, erro
    except requests.exceptions.RequestException as e:
        erro = f"Erro ao conectar com a API: {str(e)}"
        logger.error(erro)
        return None, erro
    except Exception as e:
        erro = f"Erro inesperado: {str(e)}"
        logger.exception("Erro inesperado ao processar documento")
        return None, erro


def main():
    # Header
    st.markdown('<div class="main-header">⚖️ Simplificador de Documentos Jurídicos</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Transforme textos jurídicos complexos em linguagem simples e verifique a correção das citações legais</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("ℹ️ Sobre")
        st.info("""
        Este sistema:
        - 📝 Simplifica linguagem jurídica
        - 🔍 Verifica citações de leis
        - ⚠️ Identifica discrepâncias
        - 📚 Busca legislação atualizada
        """)
        
        st.header("⚙️ Configurações")
        api_url = st.text_input("URL da API", value="http://localhost:8000")
        
        st.header("📖 Exemplo")
        if st.button("Carregar Texto de Exemplo"):
            logger.info("Usuário carregou texto de exemplo")
            st.session_state.texto_exemplo = True
            st.rerun()
    
    # Texto de exemplo
    texto_exemplo = """O contratante, doravante denominado CONTRATANTE, nos termos do artigo 421 do Código Civil (Lei 10.406/2002), obriga-se a adimplir as prestações pecuniárias conforme artigo 394 do mesmo diploma legal, sob pena de incorrer em mora nos termos do artigo 389.

Conforme disposto no artigo 6º da Lei 8.078/90 (Código de Defesa do Consumidor), são direitos básicos do consumidor a proteção da vida, saúde e segurança contra os riscos provocados por práticas no fornecimento de produtos e serviços considerados perigosos ou nocivos.

O inadimplemento contratual ensejará a aplicação de multa moratória de 2% ao mês, conforme artigo 52 da Lei 8.078/90, além de juros de mora de 1% ao mês."""
    
    # Input de texto
    st.header("📄 Documento Original")
    
    if 'texto_exemplo' in st.session_state and st.session_state.texto_exemplo:
        texto_input = st.text_area(
            "Cole aqui o texto jurídico que deseja analisar:",
            value=texto_exemplo,
            height=300,
            key="texto_area"
        )
        st.session_state.texto_exemplo = False
    else:
        texto_input = st.text_area(
            "Cole aqui o texto jurídico que deseja analisar:",
            height=300,
            placeholder="Cole seu texto aqui...",
            key="texto_area"
        )
    
    col1, col2 = st.columns([3, 1])
    with col1:
        processar = st.button("🚀 Processar Documento", use_container_width=True)
    with col2:
        limpar = st.button("🗑️ Limpar", use_container_width=True)
    
    if limpar:
        logger.info("Usuário limpou a sessão")
        st.session_state.clear()
        st.rerun()
    
    # Processamento
    if processar:
        if not texto_input.strip():
            logger.warning("Tentativa de processar documento vazio")
            st.error("⚠️ Por favor, insira um texto para processar.")
        else:
            with st.spinner("🔄 Processando documento... Isso pode levar alguns instantes."):
                resultado, erro = processar_documento_api(texto_input, api_url)
                
                if erro:
                    st.error(f"❌ {erro}")
                    st.info("💡 Certifique-se de que a API está rodando com: `uvicorn api:app --reload`")
                else:
                    logger.info("Resultado armazenado na sessão para exibição")
                    st.session_state.resultado = resultado
    
    # Exibir resultados
    if 'resultado' in st.session_state:
        resultado = st.session_state.resultado
        
        st.markdown("---")
        
        # Texto Simplificado
        st.header("✨ Texto Simplificado")
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.write(resultado['textoSimplificado'])
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.button("📋 Copiar Texto Simplificado"):
            logger.info("Usuário solicitou cópia do texto simplificado")
            st.code(resultado['textoSimplificado'], language=None)
            st.success("✅ Texto copiado! Use Ctrl+C para copiar do bloco acima.")
        
        st.markdown("---")
        
        # Análise de Discrepâncias
        st.header("🔍 Análise de Citações Legais")
        
        if resultado['discrepancias']:
            for i, disc in enumerate(resultado['discrepancias'], 1):
                if disc['tipo'] == 'erro':
                    st.markdown('<div class="error-box">', unsafe_allow_html=True)
                    icon = "❌"
                    cor = "🔴"
                elif disc['tipo'] == 'alerta':
                    st.markdown('<div class="warning-box">', unsafe_allow_html=True)
                    icon = "⚠️"
                    cor = "🟡"
                else:
                    st.markdown('<div class="success-box">', unsafe_allow_html=True)
                    icon = "✅"
                    cor = "🟢"
                
                st.markdown(f"### {icon} {disc['artigo']}")
                st.markdown(f"**Gravidade:** {cor} {disc['gravidade'].upper()}")
                
                if disc.get('textoOriginal'):
                    st.markdown(f"**Trecho:** *\"{disc['textoOriginal']}\"*")
                
                if disc.get('problemaEncontrado'):
                    st.markdown(f"**⚠️ Problema:** {disc['problemaEncontrado']}")
                
                if disc.get('artigoCorreto'):
                    st.markdown(f"**📌 Artigo Correto:** {disc['artigoCorreto']}")
                
                st.markdown(f"**💡 Sugestão:** {disc['sugestao']}")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Nenhuma discrepância encontrada ou análise não disponível.")
        
        st.markdown("---")
        
        # Legislação Consultada
        st.header("📚 Legislação Consultada")
        
        if resultado['leisEncontradas']:
            for lei in resultado['leisEncontradas']:
                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                st.markdown(f"**📖 {lei['nome']}**")
                st.markdown(f"*Status:* {lei['status']}")
                st.markdown(f"[🔗 Acessar Legislação]({lei['link']})")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("ℹ️ Nenhuma legislação específica foi identificada.")
        
        # Download do relatório
        st.markdown("---")
        relatorio = f"""RELATÓRIO DE SIMPLIFICAÇÃO E ANÁLISE JURÍDICA
{'='*80}

TEXTO SIMPLIFICADO:
{resultado['textoSimplificado']}

{'='*80}

ANÁLISE DE DISCREPÂNCIAS:

{chr(10).join([f'''
{i}. {d['artigo']}
   Gravidade: {d['gravidade'].upper()}
   Status: {'❌ ERRO' if d['tipo'] == 'erro' else '⚠️ ALERTA' if d['tipo'] == 'alerta' else '✅ OK'}
   {f"Problema: {d['problemaEncontrado']}" if d.get('problemaEncontrado') else ''}
   Sugestão: {d['sugestao']}
''' for i, d in enumerate(resultado['discrepancias'], 1)])}

{'='*80}

LEGISLAÇÃO CONSULTADA:
{chr(10).join([f'''
• {lei['nome']}
  Status: {lei['status']}
  Link: {lei['link']}
''' for lei in resultado['leisEncontradas']])}
"""
        
        if st.download_button(
            label="📥 Download Relatório Completo",
            data=relatorio,
            file_name="relatorio_juridico.txt",
            mime="text/plain",
            use_container_width=True
        ):
            logger.info("Usuário realizou download do relatório completo")


if __name__ == "__main__":
    main()