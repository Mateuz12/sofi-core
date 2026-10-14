import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import tempfile
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from departments.financeiro.modules.xml.gerador_relatorio_detalhado import processar_relatorios_detalhados

class TestIntegracaoGeradorDetalhado(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_pipeline_invocacao_detalhado(self):
        """Verifica se processar_relatorios_detalhados opera corretamente quando chamado com lista de XMLs."""
        xml_teste = """<?xml version="1.0" encoding="utf-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe>
    <infNFe>
      <ide><nNF>7777</nNF><dhEmi>2025-08-01T10:00:00-03:00</dhEmi></ide>
      <dest><CNPJ>20798658000431</CNPJ></dest>
      <det nItem="1"><prod><cProd>SKU-INTEGRACAO</cProd><qCom>50</qCom></prod></det>
    </infNFe>
  </NFe>
</nfeProc>"""
        caminho_xml = os.path.join(self.temp_dir.name, "nota_integracao.xml")
        with open(caminho_xml, "w", encoding="utf-8") as f:
            f.write(xml_teste)

        diretorio_saida = os.path.join(self.temp_dir.name, "RELATORIOS_DETALHADOS")
        mapa_mock = {
            '20798658000431': {'PDV': '20844', 'Nomenclatura': 'UDI VD CAPTACAO', 'Canal': 'VD', 'Unidade': 'UDI'}
        }

        with patch('departments.financeiro.modules.xml.leitor_xml.LOJAS_MAP_DINAMICO', mapa_mock):
            res = processar_relatorios_detalhados(
                lista_arquivos_xml=[caminho_xml],
                diretorio_base_saida=diretorio_saida,
                ano_pasta="2025",
                mes_pasta="08 - Agosto",
                semana_pasta="Semana 01-08 a 07-08",
                pdvs_alvo=['20844', '13793']
            )

        self.assertIn('20844', res)
        self.assertTrue(os.path.exists(res['20844']))
        self.assertTrue(res['20844'].endswith("13-PUB.XML.VD.CAPTACAO.20844.NOTA FISCAL DETALHADO.Semana 01-08 a 07-08.xlsx"))

if __name__ == '__main__':
    unittest.main()
