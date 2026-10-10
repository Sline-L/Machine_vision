"""Verify compiled report using Poppler; no model execution."""
from pathlib import Path
import subprocess,re,json,hashlib,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'GearPro_技术报告/GearPro_技术报告.md'
PDF=ROOT/'Output/main.pdf'
log=(ROOT/'Output/main.log').read_text(errors='replace')
checks=[]
def check(ok,name):
 if not ok:raise AssertionError(name)
 checks.append(name)
check(not re.search(r'Overfull|Missing character|Undefined control sequence|undefined references|Citation .* undefined|LaTeX Error',log,re.I),'无越界、缺字、错误或未解析引用')
body=(ROOT/'document.tex').read_text();append=(ROOT/'TEX/appendices.tex').read_text();refs=(ROOT/'TEX/references.tex').read_text()
check(body.count(r'\section{')==5,'正文五章')
check(append.count(r'\section{')==7,'附录七组')
check((body+append).count(r'\includegraphics')==12,'完整保留12幅图')
check(refs.count(r'\bibitem{ref')==17,'完整保留17条文献')
check((body+append).count(r'\captionof{table}')+(body+append).count(r'\caption{')-12==22,'22张具名三线表')
check(not re.search(r'\[(?:[UP](?=[、，；;\]])|A\d+(?=[、，；;—–\]\-]))[^\]]*\]',body+append),'无内部来源代码')
text=subprocess.check_output(['pdftotext','-layout',str(PDF),'-']).decode()
compact=re.sub(r'\s+','',text)
for token in ['63/71','18/79','25/20/99/6','36/4/102/8','63/18/61/8','54/33/46/17','0.300273610279458','0.3413327979078584','0.20599650265366867','不能证明三个成员都必要','D.1','F.11']:
 check(token in compact,'关键结果或边界/'+token)
info=subprocess.check_output(['pdfinfo',str(PDF)]).decode();pages=int(re.search(r'Pages:\s+(\d+)',info)[1])
check('A4' in info,'A4纸张')
xml=subprocess.check_output(['pdftotext','-bbox',str(PDF),'-']).decode();tree=ET.fromstring(xml)
ns={'x':'http://www.w3.org/1999/xhtml'}
words=tree.findall('.//x:word',ns)
check(all(float(w.attrib['xMin'])>=48 and float(w.attrib['xMax'])<=548 for w in words),'文字在左右版心范围内')
blocks=[p for p in text.split('\f') if p.strip()]
appendix_start=next(i for i,p in enumerate(blocks) if re.search(r'^\s*附录\s*A\s+文献与证据的对应关系',p,re.M) and i>2)
result={'pages':pages,'frontmatter_pages':2,'body_pages':appendix_start-2,'figures':12,'tables':22,'references':17,'checks_passed':len(checks),'checks':checks,'source_markdown_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),'scope':'LaTeX_typesetting_only; no_training; no_inference; no_model_configuration_changes'}
(ROOT/'Output/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
