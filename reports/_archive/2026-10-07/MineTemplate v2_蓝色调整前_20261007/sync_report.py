'''Convert the current report Markdown into this XeLaTeX template, without inference.'''
from pathlib import Path
import re,json,shutil
from bs4 import BeautifulSoup,NavigableString
import markdown
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'GearPro_技术报告'
md=(SOURCE/'GearPro_技术报告.md').read_text(encoding='utf-8')
soup=BeautifulSoup(markdown.markdown(md,extensions=['tables','fenced_code']),'html.parser')

def esc(s):
    mapping={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}','≤':r'\ensuremath{\leq}','≥':r'\ensuremath{\geq}','×':r'\ensuremath{\times}','γ':r'\ensuremath{\gamma}','α':r'\ensuremath{\alpha}','π':r'\ensuremath{\pi}','τ':r'\ensuremath{\tau}','−':r'\ensuremath{-}','→':r'\ensuremath{\rightarrow}','∈':r'\ensuremath{\in}','—':'--','–':'--'}
    out=''.join(mapping.get(c,c) for c in s)
    return re.sub(r'\[(\d{1,2})\]',lambda m:r'\cite{ref'+m[1]+'}',out)

def inline(node):
    if isinstance(node,NavigableString):
        chunks=re.split(r'(\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+){2,}\b)',str(node))
        return ''.join((r'\ReportCode{'+x+'}') if i%2 else esc(x) for i,x in enumerate(chunks))
    text=''.join(inline(c) for c in node.children)
    if node.name=='a':
        if node.get('id'):return r'\ReportAnchor{'+node['id']+'}'+text
        href=node.get('href','')
        if href.startswith('#'):return r'\protect\hyperlink{'+href[1:]+'}{'+text+'}'
        if not href.startswith(('http:','https:')):
            target=(SOURCE/href).resolve()
            import os
            href='run:'+os.path.relpath(target,ROOT)
        return r'\protect\href{'+href.replace('%',r'\%').replace('#',r'\#')+'}{'+text+'}'
    if node.name in ['strong','b']:return r'\textbf{'+text+'}'
    if node.name in ['em','i']:return text # 中文不使用伪斜体
    if node.name=='code':
        raw=node.get_text()
        formulas={
          'logit(p)=ln[p/(1−p)]':r'$\operatorname{logit}(p)=\ln[p/(1-p)]$',
          'p_T=sigmoid(logit(p)/T)':r'$p_T=\operatorname{sigmoid}(\operatorname{logit}(p)/T)$',
          'c=(s_Eff+s_Res)/2':r'$c=(s_{\mathrm{Eff}}+s_{\mathrm{Res}})/2$',
          'f_α=αc+(1−α)s_det':r'$f_\alpha=\alpha c+(1-\alpha)s_{\mathrm{det}}$',
          'q=(TP+FP)/N':r'$q=(\mathrm{TP}+\mathrm{FP})/N$',
          'Precision=πR/[πR+(1−π)FPR]':r'$\mathrm{Precision}=\pi R/[\pi R+(1-\pi)\mathrm{FPR}]$',
          'q=πR+(1−π)FPR':r'$q=\pi R+(1-\pi)\mathrm{FPR}$',
          'REJECT=(s_scratch≥τ_scratch) OR (s_missing≥τ_missing)':r'$\mathrm{REJECT}=(s_{\mathrm{scratch}}\geq\tau_{\mathrm{scratch}})\lor(s_{\mathrm{missing}}\geq\tau_{\mathrm{missing}})$',
          'L = mean[w_y × (1−p_t)^γ × BCE(z,y)]':r'$L=\operatorname{mean}[w_y(1-p_t)^\gamma\operatorname{BCE}(z,y)]$',
          'w_i=1/n_(label,view或position)':r'$w_i=1/n_{(\mathrm{label},\,\mathrm{view\ or\ position})}$',
        }
        if raw in formulas:return formulas[raw]
        if re.search(r'[\u4e00-\u9fff]',raw):return esc(raw)
        return r'\ReportCode{'+raw.replace('|','/')+'}'
    if node.name=='br':return r'\newline '
    return text

table_index=0
table_titles=['自建图像数据划分','V3图像判断与区域定位的不同评价单位','V4排序指标与所选工作点','划痕单模型与融合验证对照','齿部缺损单模型与融合验证对照','评价指标与模型参数的区别','最终融合系数及判定阈值','固定配置的图像级测试结果','下一阶段验证优先级','文献支持与项目证据边界','固定训练参数摘要','实验资料与配置来源目录','术语与实际方法定义','数据规模及各任务正负样本定义','V4配置与历史结果来源','未采用配置及已有观察','最终成员系数、温度及阈值','人工复核评价框架','参数来源完整表','单模型与融合完整验证记录','软件与原型状态','后续实验与评价方法']
def table(node):
    global table_index
    title=table_titles[table_index];table_index+=1
    rows=node.find_all('tr');n=len(rows[0].find_all(['th','td']))
    first=rows[0].get_text(' ',strip=True)
    if n==7:weights=[.07,.20,.17,.07,.24,.11,.14]
    elif '可核对文件' in first:weights=[.22,.33,.45]
    elif '每图分类前向次数' in first:weights=[.22,.12,.24,.24,.18]
    elif n==6:weights=[.16,.14,.14,.14,.24,.18]
    elif n==5:weights=[.26,.26,.16,.16,.16]
    elif n==4 and '验证方案' in first:weights=[.38,.09,.27,.26]
    elif n==4:weights=[.23,.26,.26,.25]
    elif n==3:weights=[.24,.34,.42]
    elif n==2:weights=[.38,.62]
    else:weights=[1/n]*n
    spec='@{}'+''.join(r'>{\raggedright\arraybackslash}p{'+f'{w:.3f}'+r'\dimexpr\linewidth-'+str(2*(n-1))+r'\tabcolsep\relax}' for w in weights)+'@{}'
    def row(tr):return ' & '.join(inline(c) for c in tr.find_all(['td','th'],recursive=False))+r' \\'+'\n'
    header=row(rows[0])
    contents=''.join(row(x) for x in rows[1:])
    if len(rows)<=7:
        # 小表整体排版，避免只有一两行被拆到下一页。
        return '\n'+r'\par\medskip\noindent\begin{minipage}{\linewidth}\small\setstretch{1.06}'+'\n'+r'\captionof{table}{'+title+'}\n'+r'\begin{tabular}{'+spec+'}\n'+r'\toprule'+'\n'+header+r'\midrule'+'\n'+contents+r'\bottomrule\end{tabular}\end{minipage}\par\medskip'+'\n\n'
    return '\n'+r'\begingroup\small\setstretch{1.06}'+'\n'+r'\begin{longtable}{'+spec+'}\n'+r'\caption{'+title+r'}\\'+'\n'+r'\toprule'+'\n'+header+r'\midrule\endfirsthead'+'\n'+r'\toprule'+'\n'+header+r'\midrule\endhead'+'\n'+r'\midrule\multicolumn{'+str(n)+r'}{r}{\footnotesize 续下页}\endfoot'+'\n'+r'\bottomrule\endlastfoot'+'\n'+contents+r'\end{longtable}\endgroup'+'\n\n'

children=[c for c in soup.children if not isinstance(c,NavigableString)]
parts={'front':[],'body':[],'appendix':[],'references':[]};mode='front';i=0;figure_num=0
while i<len(children):
    node=children[i];i+=1
    if node.name=='h1':continue
    if node.name=='h2':
        txt=node.get_text()
        if txt.startswith('参考文献'):mode='references';continue
        if txt.startswith('附录'):mode='appendix';title=re.sub(r'^附录[A-G]\s*','',txt)
        else:mode='body';title=re.sub(r'^\d+\s*','',txt)
        parts[mode].append(r'\FloatBarrier\Needspace{5\baselineskip}\section{'+esc(title)+'}\n');continue
    if mode=='references':
        # 参考文献项保持原编号和出版信息，不依赖外部BibTeX样式重排。
        txt=node.get_text();m=re.match(r'\[(\d+)\]',txt)
        if m:
            strong=node.find('strong');strong.extract()
            parts[mode].append(r'\bibitem{ref'+m[1]+'} '+inline(node)+'\n\n')
        continue
    if node.name=='h3':
        if mode=='front':continue
        title=re.sub(r'^(?:\d+\.\d+|[A-G]\.\d+)\s*','',node.get_text())
        parts[mode].append(r'\FloatBarrier\Needspace{4\baselineskip}\subsection{'+esc(title)+'}\n');continue
    if node.name=='table':parts[mode].append(table(node));continue
    if node.name=='p' and node.find('img'):
        img=node.find('img');name=Path(img['src']).name
        cap=children[i] if i<len(children) and children[i].name=='p' and children[i].find('em') else None
        if cap:i+=1
        caption=inline(cap) if cap else esc(img.get('alt',''))
        caption=re.sub(r'^图\d+\s*','',caption)
        figure_num+=1
        # 大图保留可读尺寸，并限制高宽以便正常浮动。
        parts[mode].append(r'\begin{figure}[H]\centering'+'\n'+r'\includegraphics[width=\linewidth,height=0.37\textheight,keepaspectratio]{'+name+'}\n'+r'\caption{'+caption+'}\n'+r'\label{fig:report-'+str(figure_num)+'}\n'+r'\end{figure}'+'\n\n');continue
    if node.name=='blockquote':
        parts[mode].append(r'\ReportNote{'+inline(node)+'}\n');continue
    if node.name in ['ul','ol']:
        env='itemize' if node.name=='ul' else 'enumerate'
        parts[mode].append(r'\begin{'+env+'}\n'+''.join(r'\item '+inline(x)+'\n' for x in node.find_all('li',recursive=False))+r'\end{'+env+'}\n');continue
    if node.name=='p':
        if mode=='front' and node.get_text().startswith('阶段研究报告'):continue
        if node.find('em') and len(node.contents)==1:parts[mode].append(r'\ReportNote{'+inline(node)+'}\n')
        else:parts[mode].append(inline(node)+'\n\n')
    else:parts[mode].append(inline(node)+'\n')
front=r'''\thispagestyle{plain}
\noindent{\small\sffamily\color{GearTeal}GEARPRO\quad /\quad 阶段研究报告}\par
\vspace{1.1cm}
\noindent{\fontsize{29}{37}\selectfont\sffamily\bfseries\color{GearInk}齿轮外观缺陷检测\par}
\vspace{0.2cm}
\noindent{\fontsize{23}{31}\selectfont\sffamily\bfseries\color{GearInk}系统技术报告\par}
\vspace{0.55cm}
\noindent{\large\color{GearMuted}自建数据 · 两类缺陷选型 · 参数依据 · 软件集成}\par
\vspace{0.4cm}
\noindent{\small\color{GearMuted}GearPro\quad 阶段记录日期：2026年10月7日}\par
\vspace{0.55cm}
\noindent\textcolor{GearTeal}{\rule{\linewidth}{1.1pt}}\par
\vspace{0.4cm}
\noindent{\large\sffamily\bfseries 摘要}\par\medskip
'''+''.join(parts['front'])
(ROOT/'TEX/frontmatter.tex').write_text(front,encoding='utf-8')
(ROOT/'document.tex').write_text('% !TEX root = main.tex\n% 正文以图像评价为单位，保留原始实验数值。\n'+''.join(parts['body']),encoding='utf-8')
(ROOT/'TEX/appendices.tex').write_text('% !TEX root = ../main.tex\n'+''.join(parts['appendix']),encoding='utf-8')
refs=r'\phantomsection\addcontentsline{toc}{section}{参考文献}'+'\n'+r'\begin{thebibliography}{99}\small\raggedright\setstretch{1.08}'+'\n'+''.join(parts['references'])+r'\end{thebibliography}'+'\n'
(ROOT/'TEX/references.tex').write_text(refs,encoding='utf-8')
# BibTeX作为可迁移的资料导出，当前PDF由references.tex保留既有数字顺序。
bib=[]
ref_soup=BeautifulSoup(markdown.markdown(md.split('## 参考文献')[1]),'html.parser')
for p in ref_soup.find_all('p'):
    m=re.match(r'\[(\d+)\]',p.get_text());a=p.find('a')
    if not m or not a:continue
    author=p.get_text().split(a.get_text())[0].replace('['+m[1]+']','').strip(' .')
    years=re.findall(r'\b(?:19|20)\d{2}\b',p.get_text());year=years[0] if years else '2026'
    bib.append('@misc{ref'+m[1]+',\n  author = {'+author+'},\n  title = {'+a.get_text()+'},\n  year = {'+year+'},\n  url = {'+a['href']+'},\n  note = {完整出版信息见 TEX/references.tex}\n}\n')
(ROOT/'references.bib').write_text('% 可迁移参考资料；当前排版使用TEX/references.tex。\n'+'\n'.join(bib),encoding='utf-8')
for image in (SOURCE/'assets').glob('*.png'):shutil.copy2(image,ROOT/'pictures/report'/image.name)
print(json.dumps({'figures':figure_num,'references':len(parts['references']),'source':str(SOURCE/'GearPro_技术报告.md')},ensure_ascii=False))
