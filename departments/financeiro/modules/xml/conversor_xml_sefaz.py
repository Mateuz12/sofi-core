# -*- coding: utf-8 -*-
"""
conversor_xml_sefaz.py
======================
Converte XMLs de NF-e baixadas via API MeuDanfe para o padrão estrutural
oficial da SEFAZ (nfeProc versão 4.00).

As XMLs do MeuDanfe possuem os mesmos dados fiscais, porém com:
  - Ordem dos blocos invertida (protNFe antes de NFe)
  - Atributos como subelementos (nItem, Id, versao)
  - Ordem interna dos elementos fora do padrão SEFAZ em TODOS os níveis
  - Atributos xmlns e versao ausentes no protNFe

Este script NÃO adiciona a assinatura digital (<Signature>), pois ela é
gerada com o certificado digital do emitente e não é necessária para uso
interno de relatórios e contabilização.

Uso standalone:
    python conversor_xml_sefaz.py "T:\\...\\Semana 06-07 a 12-07"
    python conversor_xml_sefaz.py --backup "T:\\...\\Semana 06-07 a 12-07"
    python conversor_xml_sefaz.py --arquivo "T:\\...\\20846\\20846_656344.xml"
"""

import os
import sys
import argparse
import shutil
import re
from pathlib import Path
from lxml import etree

# ============================================================================
# NAMESPACES
# ============================================================================
NS_NFE  = "http://www.portalfiscal.inf.br/nfe"
NS_SIG  = "http://www.w3.org/2000/09/xmldsig#"
NS_MAP  = {"nfe": NS_NFE}

# ============================================================================
# ORDENS CANÔNICAS — Manual de Integração NF-e v4.00 SEFAZ
# Cada dicionário mapeia o nome local do elemento pai → lista ordenada de filhos
# ============================================================================

ORDENS_SEFAZ = {
    # Filhos de <infNFe>
    "infNFe": [
        "ide", "emit", "avulsa", "dest", "retirada", "entrega",
        "autXML", "det", "total", "transp", "cobr", "pag",
        "infIntermed", "infAdic", "exporta", "compra", "cana",
        "infRespTec", "infSolicNFF",
    ],
    # Filhos de <ide>
    "ide": [
        "cUF", "cNF", "natOp", "mod", "serie", "nNF", "dhEmi", "dhSaiEnt",
        "tpNF", "idDest", "cMunFG", "tpImp", "tpEmis", "cDV", "tpAmb",
        "finNFe", "indFinal", "indPres", "indIntermed", "procEmi", "verProc",
        "dhCont", "xJust", "NFref",
    ],
    # Filhos de <emit>
    "emit": [
        "CNPJ", "CPF", "xNome", "xFant", "enderEmit", "IE", "IEST", "IM",
        "CNAE", "CRT",
    ],
    # Filhos de <enderEmit>
    "enderEmit": [
        "xLgr", "nro", "xCpl", "xBairro", "cMun", "xMun", "UF", "CEP",
        "cPais", "xPais", "fone",
    ],
    # Filhos de <dest>
    "dest": [
        "CNPJ", "CPF", "idEstrangeiro", "xNome", "enderDest", "indIEDest",
        "IE", "ISUF", "IM", "email",
    ],
    # Filhos de <enderDest>
    "enderDest": [
        "xLgr", "nro", "xCpl", "xBairro", "cMun", "xMun", "UF", "CEP",
        "cPais", "xPais", "fone",
    ],
    # Filhos de <prod>
    "prod": [
        "cProd", "cEAN", "cBarra", "xProd", "NCM", "NVE", "CEST", "indEscala",
        "CNPJFab", "cBenef", "EXTIPI", "CFOP", "uCom", "qCom", "vUnCom",
        "vProd", "cEANTrib", "cBarraTrib", "uTrib", "qTrib", "vUnTrib",
        "vFrete", "vSeg", "vDesc", "vOutro", "indTot", "DI", "detExport",
        "xPed", "nItemPed", "nFCI", "rastro", "infProdNFF", "infProdEmb",
        "veicProd", "med", "arma", "comb", "nRECOPI",
    ],
    # Filhos de <imposto>
    "imposto": [
        "vTotTrib", "ICMS", "IPI", "II", "PIS", "PISST", "COFINS",
        "COFINSST", "ISSQN", "ICMSUFDest", "IBSCBS",
    ],
    # Filhos de <ICMS10>
    "ICMS10": [
        "orig", "CST", "modBC", "vBC", "pICMS", "vICMS", "vBCFCP", "pFCP",
        "vFCP", "modBCST", "pMVAST", "vBCST", "pICMSST", "vICMSST",
        "vBCFCPST", "pFCPST", "vFCPST",
    ],
    # Filhos de <ICMS00>
    "ICMS00": [
        "orig", "CST", "modBC", "vBC", "pICMS", "vICMS", "pFCP", "vFCP",
    ],
    # Filhos de <ICMS20>
    "ICMS20": [
        "orig", "CST", "modBC", "pRedBC", "vBC", "pICMS", "vICMS",
        "vBCFCP", "pFCP", "vFCP", "vICMSDeson", "motDesICMS",
    ],
    # Filhos de <ICMS30>
    "ICMS30": [
        "orig", "CST", "modBCST", "pMVAST", "pRedBCST", "vBCST",
        "pICMSST", "vICMSST", "vBCFCPST", "pFCPST", "vFCPST",
        "vICMSDeson", "motDesICMS",
    ],
    # Filhos de <ICMS40> / <ICMS41> / <ICMS50>
    "ICMS40": ["orig", "CST", "vICMSDeson", "motDesICMS"],
    "ICMS41": ["orig", "CST", "vICMSDeson", "motDesICMS"],
    "ICMS50": ["orig", "CST", "vICMSDeson", "motDesICMS"],
    # Filhos de <ICMS51>
    "ICMS51": [
        "orig", "CST", "modBC", "pRedBC", "vBC", "pICMS", "vICMSOp",
        "pDif", "vICMSDif", "vICMS", "vBCFCP", "pFCP", "vFCP",
    ],
    # Filhos de <ICMS60>
    "ICMS60": [
        "orig", "CST", "vBCSTRet", "pST", "vICMSSubstituto",
        "vICMSSTRet", "vBCFCPSTRet", "pFCPSTRet", "vFCPSTRet",
        "pRedBCEfet", "vBCEfet", "pICMSEfet", "vICMSEfet",
    ],
    # Filhos de <ICMS70>
    "ICMS70": [
        "orig", "CST", "modBC", "pRedBC", "vBC", "pICMS", "vICMS",
        "vBCFCP", "pFCP", "vFCP", "modBCST", "pMVAST", "pRedBCST",
        "vBCST", "pICMSST", "vICMSST", "vBCFCPST", "pFCPST", "vFCPST",
        "vICMSDeson", "motDesICMS",
    ],
    # Filhos de <ICMS90>
    "ICMS90": [
        "orig", "CST", "modBC", "vBC", "pRedBC", "pICMS", "vICMS",
        "vBCFCP", "pFCP", "vFCP", "modBCST", "pMVAST", "pRedBCST",
        "vBCST", "pICMSST", "vICMSST", "vBCFCPST", "pFCPST", "vFCPST",
        "vICMSDeson", "motDesICMS",
    ],
    # Filhos de <ICMSSN101> a <ICMSSN900> (Simples Nacional)
    "ICMSSN101": ["orig", "CSOSN", "pCredSN", "vCredICMSSN"],
    "ICMSSN102": ["orig", "CSOSN"],
    "ICMSSN201": [
        "orig", "CSOSN", "modBCST", "pMVAST", "pRedBCST", "vBCST",
        "pICMSST", "vICMSST", "vBCFCPST", "pFCPST", "vFCPST",
        "pCredSN", "vCredICMSSN",
    ],
    "ICMSSN202": [
        "orig", "CSOSN", "modBCST", "pMVAST", "pRedBCST", "vBCST",
        "pICMSST", "vICMSST", "vBCFCPST", "pFCPST", "vFCPST",
    ],
    "ICMSSN500": [
        "orig", "CSOSN", "vBCSTRet", "pST", "vICMSSubstituto",
        "vICMSSTRet", "vBCFCPSTRet", "pFCPSTRet", "vFCPSTRet",
    ],
    "ICMSSN900": [
        "orig", "CSOSN", "modBC", "vBC", "pRedBC", "pICMS", "vICMS",
        "modBCST", "pMVAST", "pRedBCST", "vBCST", "pICMSST", "vICMSST",
        "vBCFCPST", "pFCPST", "vFCPST", "pCredSN", "vCredICMSSN",
    ],
    # Filhos de <IPI>
    "IPI": [
        "CNPJProd", "cSelo", "qSelo", "cEnq", "IPITrib", "IPINT",
    ],
    # Filhos de <IPITrib>
    "IPITrib": ["CST", "vBC", "pIPI", "qUnid", "vUnid", "vIPI"],
    # Filhos de <IPINT>
    "IPINT": ["CST"],
    # Filhos de <PIS>
    "PIS": ["PISAliq", "PISQtde", "PISNT", "PISOutr"],
    # Filhos de <PISNT>
    "PISNT": ["CST"],
    # Filhos de <PISAliq>
    "PISAliq": ["CST", "vBC", "pPIS", "vPIS"],
    # Filhos de <PISOutr>
    "PISOutr": ["CST", "vBC", "pPIS", "qBCProd", "vAliqProd", "vPIS"],
    # Filhos de <COFINS>
    "COFINS": ["COFINSAliq", "COFINSQtde", "COFINSNT", "COFINSOutr"],
    # Filhos de <COFINSNT>
    "COFINSNT": ["CST"],
    # Filhos de <COFINSAliq>
    "COFINSAliq": ["CST", "vBC", "pCOFINS", "vCOFINS"],
    # Filhos de <COFINSOutr>
    "COFINSOutr": ["CST", "vBC", "pCOFINS", "qBCProd", "vAliqProd", "vCOFINS"],
    # Filhos de <IBSCBS>
    "IBSCBS": ["CST", "cClassTrib", "gIBSCBS"],
    # Filhos de <gIBSCBS>
    "gIBSCBS": ["vBC", "gIBSUF", "gIBSMun", "vIBS", "gCBS"],
    # Filhos de <gIBSUF>
    "gIBSUF": ["pIBSUF", "vIBSUF", "vDif", "vDevTrib"],
    # Filhos de <gIBSMun>
    "gIBSMun": ["pIBSMun", "vIBSMun", "vDif", "vDevTrib"],
    # Filhos de <gCBS>
    "gCBS": ["pCBS", "vCBS", "vDif", "vDevTrib"],
    # Filhos de <total>
    "total": ["ICMSTot", "ISSQNtot", "retTrib", "IBSCBSTot"],
    # Filhos de <ICMSTot>
    "ICMSTot": [
        "vBC", "vICMS", "vICMSDeson", "vFCPUFDest", "vICMSUFDest",
        "vICMSUFRemet", "vFCP", "vBCST", "vST", "vFCPST", "vFCPSTRet",
        "vProd", "vFrete", "vSeg", "vDesc", "vII", "vIPI", "vIPIDevol",
        "vPIS", "vCOFINS", "vOutro", "vNF", "vTotTrib",
    ],
    # Filhos de <IBSCBSTot>
    "IBSCBSTot": [
        "vBCIBSCBS", "gIBS", "gCBS", "gEstornoCred",
    ],
    # Filhos de <transp>
    "transp": [
        "modFrete", "transporta", "retTransp", "veicTransp", "reboque",
        "vagao", "balsa", "vol",
    ],
    # Filhos de <transporta>
    "transporta": ["CNPJ", "CPF", "xNome", "IE", "xEnder", "xMun", "UF"],
    # Filhos de <vol>
    "vol": ["qVol", "esp", "marca", "nVol", "pesoL", "pesoB", "lacres"],
    # Filhos de <cobr>
    "cobr": ["fat", "dup"],
    # Filhos de <fat>
    "fat": ["nFat", "vOrig", "vDesc", "vLiq"],
    # Filhos de <dup>
    "dup": ["nDup", "dVenc", "vDup"],
    # Filhos de <pag>
    "pag": ["detPag", "vTroco"],
    # Filhos de <detPag>
    "detPag": ["indPag", "tPag", "vPag", "card"],
    # Filhos de <infAdic>
    "infAdic": ["infAdFisco", "infCpl", "obsCont", "obsFisco", "procRef"],
    # Filhos de <infRespTec>
    "infRespTec": ["CNPJ", "xContato", "email", "fone", "idCSRT", "hashCSRT"],
    # Filhos de <infProt>
    "infProt": [
        "tpAmb", "verAplic", "chNFe", "dhRecbto",
        "nProt", "digVal", "cStat", "xMotivo",
    ],
}


# ============================================================================
# UTILITÁRIOS
# ============================================================================

def _tag_local(element):
    """Retorna o nome local da tag sem namespace."""
    tag = element.tag
    if "}" in tag:
        return tag.split("}")[1]
    return tag


def _find_text(element, local_name):
    """Busca texto de um subelemento pelo nome local, ignorando namespace."""
    for child in element:
        if _tag_local(child) == local_name:
            return child.text or ""
    return ""


def _remove_child_by_local(element, local_name):
    """Remove o primeiro filho com o nome local dado."""
    for child in element:
        if _tag_local(child) == local_name:
            element.remove(child)
            return True
    return False


def _reorder_children(element, order):
    """
    Reordena os filhos de `element` conforme a lista `order`.
    Elementos não listados em `order` ficam no final, na ordem original.
    """
    children = list(element)
    if not children:
        return

    # Preserva a posição original dos não-listados
    original_positions = {id(c): i for i, c in enumerate(children)}

    def priority(child):
        name = _tag_local(child)
        try:
            return (0, order.index(name))
        except ValueError:
            return (1, original_positions[id(child)])

    children.sort(key=priority)

    # Reconstrói a árvore na nova ordem
    for child in children:
        element.remove(child)
    for child in children:
        element.append(child)


def _reorder_recursive(element):
    """
    Aplica a reordenação SEFAZ recursivamente em `element` e em todos
    os seus descendentes que tenham uma ordem definida em ORDENS_SEFAZ.
    """
    local = _tag_local(element)
    if local in ORDENS_SEFAZ:
        _reorder_children(element, ORDENS_SEFAZ[local])

    for child in element:
        _reorder_recursive(child)


# ============================================================================
# LÓGICA DE CONVERSÃO
# ============================================================================

def converter_xml(caminho_xml: str) -> tuple[bool, str]:
    """
    Converte uma única XML do formato MeuDanfe para o padrão SEFAZ.

    Retorna:
        (True, mensagem_ok) em caso de sucesso
        (False, mensagem_erro) em caso de falha
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True, encoding="utf-8")
        tree = etree.parse(caminho_xml, parser)
        root = tree.getroot()
    except Exception as e:
        return False, f"Erro ao parsear: {e}"

    tag_raiz = _tag_local(root)
    if tag_raiz != "nfeProc":
        return False, f"Tag raiz inesperada: '{tag_raiz}'. Esperado 'nfeProc'."

    # ── 1. Garante atributo versao no <nfeProc> ─────────────────────────────
    # Remove versao como subelemento se existir (formato MeuDanfe coloca como tag)
    _remove_child_by_local(root, "versao")

    # Garante atributo versao (lxml cuida do xmlns automaticamente ao serializar)
    root.set("versao", "4.00")

    # ── 2. Localiza <NFe> e <protNFe> ───────────────────────────────────────
    nfe_elem    = None
    prot_elem   = None

    for child in list(root):
        local = _tag_local(child)
        if local == "NFe":
            nfe_elem = child
        elif local == "protNFe":
            prot_elem = child

    if nfe_elem is None:
        return False, "Elemento <NFe> não encontrado."
    if prot_elem is None:
        return False, "Elemento <protNFe> não encontrado."

    # ── 3. Garante a ordem: NFe primeiro, depois protNFe ───────────────────
    root.remove(nfe_elem)
    root.remove(prot_elem)
    root.append(nfe_elem)
    root.append(prot_elem)

    # ── 4. Processa <NFe> → <infNFe> ────────────────────────────────────────
    infNFe = None
    for child in nfe_elem:
        if _tag_local(child) == "infNFe":
            infNFe = child
            break

    if infNFe is not None:
        # 4a. Converte subelemento <Id> → atributo Id
        id_text = _find_text(infNFe, "Id")
        if id_text:
            _remove_child_by_local(infNFe, "Id")

        # 4b. Garante atributos versao e Id na ordem correta
        # lxml preserva a ordem de inserção dos atributos, então
        # recriamos ambos na ordem desejada: versao primeiro, Id depois
        versao_val = infNFe.attrib.pop("versao", "4.00")
        id_val = infNFe.attrib.pop("Id", id_text or "")
        infNFe.set("versao", versao_val)
        if id_val:
            infNFe.set("Id", id_val)

        # 4c. Converte subelemento <nItem> em atributo de cada <det>
        for det in infNFe:
            if _tag_local(det) != "det":
                continue
            n_item_text = _find_text(det, "nItem")
            if n_item_text:
                det.set("nItem", n_item_text)
                _remove_child_by_local(det, "nItem")

        # 4d. Reordena TODOS os sub-elementos recursivamente
        _reorder_recursive(infNFe)

    # ── 5. Processa <protNFe> ────────────────────────────────────────────────
    # 5a. Adiciona atributos xmlns e versao ao <protNFe>
    prot_elem.set("xmlns", NS_NFE)
    prot_elem.set("versao", "4.00")

    # 5b. Processa <infProt>
    for inf_prot in prot_elem:
        if _tag_local(inf_prot) == "infProt":
            # Adiciona tpAmb="1" se ausente
            if _find_text(inf_prot, "tpAmb") == "":
                tp_elem = etree.SubElement(inf_prot, f"{{{NS_NFE}}}tpAmb")
                tp_elem.text = "1"
            # Adiciona verAplic se ausente (MeuDanfe v2 não envia esta tag autorizadora)
            if _find_text(inf_prot, "verAplic") == "":
                ver_elem = etree.SubElement(inf_prot, f"{{{NS_NFE}}}verAplic")
                ver_elem.text = "MeuDanfe"
            # Reordena conforme padrão SEFAZ
            _reorder_children(inf_prot, ORDENS_SEFAZ["infProt"])
            break

    # ── 6. Serializa com declaração XML e encoding utf-8 ─────────────────────
    xml_bytes = etree.tostring(
        root,
        xml_declaration=True,
        encoding="utf-8",
        pretty_print=False,
    )

    # lxml usa aspas simples na declaração XML (<?xml version='1.0'...?>),
    # o padrão SEFAZ usa aspas duplas. Também normaliza encoding para minúsculo.
    xml_str = xml_bytes.decode("utf-8")
    xml_str = re.sub(
        r"""<\?xml version='1\.0' encoding='[Uu][Tt][Ff]-8'\?>""",
        '<?xml version="1.0" encoding="utf-8"?>',
        xml_str,
        count=1,
    )

    # Salva sobrescrevendo o arquivo
    with open(caminho_xml, "w", encoding="utf-8") as f:
        f.write(xml_str)

    return True, "Convertido com sucesso."


def _e_xml_meudanfe(caminho_xml: str) -> bool:
    """
    Detecta se a XML provavelmente é do formato MeuDanfe (não está no padrão SEFAZ).
    Critério rápido: verifica se a ordem correta NFe→protNFe já está presente
    e se existem sub-elementos fora de ordem.
    """
    try:
        parser = etree.XMLParser(encoding="utf-8")
        tree = etree.parse(caminho_xml, parser)
        root = tree.getroot()
        if _tag_local(root) != "nfeProc":
            return False
        children = [_tag_local(c) for c in root]
        # Padrão SEFAZ: NFe vem antes de protNFe
        if "NFe" in children and "protNFe" in children:
            idx_nfe  = children.index("NFe")
            idx_prot = children.index("protNFe")
            # Fora de ordem → provavelmente MeuDanfe
            if idx_prot < idx_nfe:
                return True
            # Verifica também se versao é subelemento
            if "versao" in children:
                return True
        return False
    except Exception:
        return False


# ============================================================================
# INTERFACE DE CONVERSÃO (chamável externamente)
# ============================================================================

def converter_arquivo(caminho_xml: str, fazer_backup: bool = False) -> bool:
    """
    Converte um único arquivo XML para o padrão SEFAZ.

    Args:
        caminho_xml:   Caminho absoluto do arquivo .xml
        fazer_backup:  Se True, cria cópia <nome>.xml.bak antes de converter

    Returns:
        True se convertido com sucesso, False caso contrário.
    """
    if not os.path.isfile(caminho_xml):
        print(f"  [ERRO] Arquivo não encontrado: {caminho_xml}")
        return False

    if fazer_backup:
        shutil.copy2(caminho_xml, caminho_xml + ".bak")

    ok, msg = converter_xml(caminho_xml)
    status = "OK  " if ok else "ERRO"
    print(f"  [{status}] {os.path.basename(caminho_xml)} — {msg}")
    return ok


def converter_pasta(caminho_pasta: str, fazer_backup: bool = False,
                    apenas_meudanfe: bool = True) -> dict:
    """
    Converte recursivamente todos os arquivos .xml em `caminho_pasta`
    para o padrão SEFAZ.

    Args:
        caminho_pasta:   Pasta raiz (procura recursivamente por .xml)
        fazer_backup:    Se True, cria .xml.bak antes de cada conversão
        apenas_meudanfe: Se True, pula arquivos já no padrão SEFAZ (evita
                         reprocessar arquivos já convertidos)

    Returns:
        Dicionário com contagens: {'total': N, 'convertidos': N, 'pulados': N, 'erros': N}
    """
    if not os.path.isdir(caminho_pasta):
        print(f"  [ERRO] Pasta não encontrada: {caminho_pasta}")
        return {"total": 0, "convertidos": 0, "pulados": 0, "erros": 0}

    arquivos_xml = list(Path(caminho_pasta).rglob("*.xml"))
    # Exclui arquivos de backup
    arquivos_xml = [p for p in arquivos_xml if not str(p).endswith(".bak")]

    total      = len(arquivos_xml)
    convertidos = 0
    pulados    = 0
    erros      = 0

    print(f"\n[Conversor SEFAZ] Processando {total} arquivo(s) em:")
    print(f"  {caminho_pasta}\n")

    for arq in arquivos_xml:
        caminho_str = str(arq)

        if apenas_meudanfe and not _e_xml_meudanfe(caminho_str):
            pulados += 1
            continue

        if fazer_backup:
            shutil.copy2(caminho_str, caminho_str + ".bak")

        ok, msg = converter_xml(caminho_str)
        if ok:
            convertidos += 1
            print(f"  [OK  ] {arq.parent.name}/{arq.name}")
        else:
            erros += 1
            print(f"  [ERRO] {arq.parent.name}/{arq.name} — {msg}")

    print(f"\n[Conversor SEFAZ] Concluído: "
          f"{convertidos} convertido(s) | {pulados} já no padrão | {erros} erro(s)\n")

    return {
        "total":       total,
        "convertidos": convertidos,
        "pulados":     pulados,
        "erros":       erros,
    }


# ============================================================================
# ENTRY POINT STANDALONE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Converte XMLs de NF-e do formato MeuDanfe para o padrão SEFAZ."
    )
    parser.add_argument(
        "pasta",
        nargs="?",
        default="",
        help="Pasta contendo XMLs por PDV (busca recursiva). "
             "Ignorado se --arquivo for fornecido.",
    )
    parser.add_argument(
        "--arquivo",
        type=str,
        default="",
        help="Converter um único arquivo XML.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Criar cópia .xml.bak antes de cada conversão.",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Converter todas as XMLs, mesmo as já no padrão SEFAZ.",
    )
    args = parser.parse_args()

    if args.arquivo:
        print(f"\n[Conversor SEFAZ] Arquivo único: {args.arquivo}")
        converter_arquivo(args.arquivo, fazer_backup=args.backup)

    elif args.pasta:
        converter_pasta(
            args.pasta,
            fazer_backup=args.backup,
            apenas_meudanfe=not args.forcar,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
