import os
import sys
import unittest
import tempfile
from pathlib import Path

# Adiciona a raiz do projeto ao sys.path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from departments.financeiro.modules.xml.leitor_xml import extrair_itens_xml

class TestLeitorItensXml(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extrair_itens_com_namespace_sefaz(self):
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe31250806147451000112550010000123451000123456" versao="4.00">
      <ide>
        <nNF>12345</nNF>
        <dhEmi>2025-08-01T14:30:00-03:00</dhEmi>
      </ide>
      <emit>
        <CNPJ>06147451000112</CNPJ>
        <xNome>CALAMO DISTRIBUIDORA</xNome>
      </emit>
      <dest>
        <CNPJ>20798658000199</CNPJ>
        <xNome>LOJA TESTE</xNome>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>SKU-100</cProd>
          <xProd>PRODUTO TESTE 1</xProd>
          <qCom>3.0000</qCom>
          <vUnCom>10.00</vUnCom>
        </prod>
      </det>
      <det nItem="2">
        <prod>
          <cProd>SKU-200</cProd>
          <xProd>PRODUTO TESTE 2</xProd>
          <qCom>7</qCom>
          <vUnCom>20.00</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>"""
        file_path = os.path.join(self.temp_dir.name, "teste_com_ns.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        itens = extrair_itens_xml(file_path)
        self.assertIsNotNone(itens)
        self.assertEqual(len(itens), 2)

        item1 = itens[0]
        self.assertEqual(item1['n_doc'], 12345)
        self.assertEqual(item1['dt_emissao'], '01/08/2025')
        self.assertEqual(item1['sku'], 'SKU-100')
        self.assertEqual(item1['quantidade'], 3)

        item2 = itens[1]
        self.assertEqual(item2['n_doc'], 12345)
        self.assertEqual(item2['dt_emissao'], '01/08/2025')
        self.assertEqual(item2['sku'], 'SKU-200')
        self.assertEqual(item2['quantidade'], 7)

    def test_extrair_itens_sem_namespace(self):
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<nfeProc versao="4.00">
  <NFe>
    <infNFe versao="4.00">
      <ide>
        <nNF>99999</nNF>
        <dhEmi>2025-08-05T09:00:00-03:00</dhEmi>
      </ide>
      <dest>
        <CNPJ>03982400000100</CNPJ>
      </dest>
      <det nItem="1">
        <prod>
          <cProd>B52-PERFUME</cProd>
          <qCom>2.5</qCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>"""
        file_path = os.path.join(self.temp_dir.name, "teste_sem_ns.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_content)

        itens = extrair_itens_xml(file_path)
        self.assertIsNotNone(itens)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]['n_doc'], 99999)
        self.assertEqual(itens[0]['sku'], 'B52-PERFUME')
        self.assertEqual(itens[0]['quantidade'], 2.5)

if __name__ == '__main__':
    unittest.main()
