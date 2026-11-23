"""Redraw presentation figures from completed CSVs; does not run experiments."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/figures/c/deck';OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],'axes.unicode_minus':False,'figure.facecolor':'#172943','axes.facecolor':'#172943','text.color':'#ffffff','axes.labelcolor':'#afc0d4','xtick.color':'#afc0d4','ytick.color':'#afc0d4','axes.edgecolor':'#afc0d4','font.size':12})
def read(p):
 with p.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
s2=read(ROOT/'results/tables/c/step2/C03_multi_disruption_summary.csv')
s3=read(ROOT/'results/tables/c/step3/C11_efficiency_auc_summary.csv')
labels=['随机中断','原始介数排序','基准单站损失排序'];colors=['#14b8a6','#4f9cf7','#f6c453']
for metric,label,name in [('unreachable_ratio','不可达OD比例','unreachable'),('efficiency_ratio','相对基线的物理OD效率','efficiency'),('mean_delta_survivors','仍可达OD平均增量（等效站）','survivors')]:
 fig,ax=plt.subplots(figsize=(10,5.4))
 for strategy,title,c in zip(['random','centrality','single_loss'],labels,colors):
  rows=[r for r in s2 if r['strategy']==strategy];x=[int(r['k']) for r in rows]
  ax.plot(x,[float(r[metric+'_mean']) for r in rows],label=title,color=c,lw=2.4)
  if strategy=='random':ax.fill_between(x,[float(r[metric+'_p025']) for r in rows],[float(r[metric+'_p975']) for r in rows],color=c,alpha=.13)
 ax.set(xlabel='关闭换乘功能的物理站数量',ylabel=label,xticks=range(0,20,2));ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.12);ax.legend(facecolor='#172943',labelcolor='white',edgecolor='none',fontsize=11)
 fig.tight_layout();fig.savefig(OUT/(name+'.png'),dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5.4))
for strategy,label,c in zip(['random','centrality','single_loss'],labels,colors):
 rows=[r for r in s3 if r['strategy']==strategy];ax.plot([int(r['penalty']) for r in rows],[float(r['auc_mean']) for r in rows],'-o',color=c,label=label,lw=2.4)
ax.set(xlabel='换乘惩罚（等效站）',ylabel='相对效率曲线面积',xticks=[0,1,2,3,5]);ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.12);ax.legend(facecolor='#172943',labelcolor='white',edgecolor='none');fig.tight_layout();fig.savefig(OUT/'auc.png',dpi=180);plt.close(fig)
