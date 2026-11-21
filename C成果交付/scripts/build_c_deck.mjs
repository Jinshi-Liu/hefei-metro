import fs from 'node:fs/promises';
const BG='#0e1b31',CARD='#172943',TEAL='#14b8a6',GOLD='#f6c453',MUTED='#afc0d4',WHITE='#ffffff';
export async function build({presentation,input}){
const t=(s,x,y,w,h,text,size=24,color=WHITE,bold=false)=>{const a=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});a.text=text;a.text.insets=0;a.text.style={fontFamily:'Microsoft YaHei',fontSize:size,color,bold};return a;};
const box=(s,x,y,w,h,color)=>s.shapes.add({geometry:'rect',position:{left:x,top:y,width:w,height:h},fill:color,line:{fill:'none',width:0}});
const card=(s,x,y,w,h,value,label)=>{box(s,x,y,w,h,CARD);t(s,x+24,y+24,w-48,65,value,42,TEAL,true);t(s,x+24,y+h-58,w-48,42,label,20,MUTED);};
const specs=[
{title:'多站换乘中断与排名稳健性',cover:true,sub:'随机与针对性中断对比　排名验证　参数敏感性',note:'C项承接A的网络与B的路径模块，使用用户本地正式运行结果。'},
{title:'从A的数据到C的多站检验',text:[['A项：统一网络','195座物理站，215个线路副本，207条运行边与21条换乘连接。'],['B项：单站出行损失','19座换乘站逐一中断，提供介数排名、单站损失排名与路径规则。'],['C项：多站与参数验证','相同网络和OD集合下，比较三种策略，并检验换乘惩罚0、1、2、3、5。']],note:'数据与网络规模见C05，B路径模块为共享代码。S1不纳入主实验。'},
{title:'同一中断预算下比较三种策略',stats:[['19','候选换乘站'],['100','随机重复序列'],['18,915','等权物理OD']],body:'随机排列、原始介数排序、基准单站损失排序\n每条序列关闭0—19座站，排名固定，不在中途中重排。\n只去除换乘连接，保留乘车、通过和上下车。',note:'基准λ=2。共2040行情景结果，随机种子20261116。合肥南站关闭3条换乘边按1座物理站计预算。'},
{title:'少量中断时，单站损失排序更早触发断连',chart:'unreachable.png',take:'关闭3座\n\n单站损失策略\n11.48%不可达\n\n介数策略 0%\n随机平均 0.33%',note:'来源C03。单站损失前3为紫庐、合肥南站、繁华大道；紫庐和繁华大道是输入网络中7号线的两处换乘接口。阴影为随机经验分位区间，非置信区间。'},
{title:'完整中断过程中，介数策略效率破坏更强',chart:'efficiency.png',take:'效率曲线面积\n\n介数　0.7261\n单站损失　0.7397\n随机平均　0.7715\n\n越小，累计破坏越强',note:'来源C04。面积对关闭比例0—1积分。结论针对完整过程，不表示每个k上介数策略均更强。'},
{title:'绕行均值下降，可能是严重受损OD退出样本',chart:'survivors.png',take:'介数策略：10→11座\n\n不可达\n11.48% → 43.10%\n\n幸存平均增量\n8.66 → 2.69\n\n均值下降并非恢复',note:'来源C02。均值只统计中断前后都可达的OD；需与不可达比例并列解读。'},
{title:'结构位置与出行损失衡量不同的重要性',table:[['站点','介数排名','单站损失排名'],['洪岗','1','9'],['市第三医院','3','12'],['紫庐','8','1'],['繁华大道','10','3'],['合肥南站','2','2']],body:'基准Spearman秩相关为0.461。\n中心性与损失存在错位，需要结合替代路径解释。',note:'来源C06，λ=2。完整19站排名散点图见C_fig5。B已发现基准错位，C扩展参数验证。'},
{title:'前三名集合稳定，高惩罚下内部次序变化',table:[['换乘惩罚','损失前三名','与基准秩相关'],['0','紫庐、合肥南站、繁华大道','0.918'],['1','紫庐、合肥南站、繁华大道','0.982'],['2','紫庐、合肥南站、繁华大道','1.000'],['3','紫庐、合肥南站、繁华大道','0.928'],['5','合肥南站、紫庐、繁华大道','0.800']],body:'结构与损失的秩相关始终为0.370—0.470。\n不能把关键站集合稳定解释为全部排名不变。',note:'来源C07。Spearman采用并列平均秩，前三名集合相同但λ=5次序交换。'},
{title:'五种换乘惩罚下，策略整体强弱顺序保持一致',chart:'auc.png',take:'五种参数均为\n\n介数策略\n破坏更强\n\n基准单站损失策略其次\n随机平均较弱',note:'来源C11。参数为0、1、2、3、5。多站中断使用相同基准关闭顺序，各参数相对自身基线归一化。不推导最优攻击策略或统计显著性。'},
{title:'从单站损失扩展到组合关系与替代性',text:[['早期薄弱组合','紫庐与繁华大道换乘同时中断，削弱7号线对外接口。'],['整体结构作用','介数策略在完整中断过程中造成更低的效率面积。'],['参数稳定性的边界','关键站集合与策略顺序稳定，站点内部排名仍会随惩罚变化。']],note:'机制解释基于输入网络拓扑。未增加客流、公交替代、容量或真实运行分钟。'},
{title:'C项交接与合并方式',text:[['表格与图形','results/tables/c保存原始结果，results/figures/c保存PNG与SVG。'],['报告与PPT','docs/c为成果说明与交接，docs/slides为同风格汇报草稿。'],['代码与数据','src复用A/B共享模块，scripts仅重绘图表；原始参数记录保留。']],note:'本包为待合并交付，不执行GitHub上传。合并时共享数据和代码先比对，避免覆盖A/B文件。'},
{title:'C项结论',stats:[['19座','单站与组合实验衔接'],['5种','换乘惩罚参数'],['100次','随机序列对照']],body:'单站损失突出，不等于多站累计破坏最强。\n结构排名与损失排名的差异在测试参数下持续存在。\n关键站前三名集合稳定，但内部次序并非完全固定。',note:'研究边界：1—8号线固定快照，物理OD等权，代价为等效站数；不估计真实乘客损失、排队或完整调度。'}
];
for(let i=input.start;i<input.end;i++){
 const a=specs[i];const s=presentation.slides.add({width:1280,height:720});s.background.fill=BG;box(s,0,0,12,720,TEAL);
 if(a.cover){box(s,80,100,340,34,CARD);t(s,88,106,330,25,'复杂系统分析 · C项阶段成果',16,TEAL,true);t(s,80,200,1120,80,a.title,48,WHITE,true);t(s,80,300,1120,55,a.sub,26,MUTED);box(s,80,385,200,4,TEAL);t(s,80,435,1100,110,'关键换乘节点识别与出行鲁棒性\n考虑绕行与换乘代价',30);t(s,80,647,1120,32,'基于1—8号线网络　19座换乘站　2026年11月 草稿',17,MUTED);}
 else{t(s,45,28,100,25,String(i+1).padStart(2,'0'),16,TEAL,true);t(s,110,30,1040,25,'C ITEM   MULTI-STATION DISRUPTION AND ROBUSTNESS',13,MUTED);t(s,54,87,1160,62,a.title,35,WHITE,true);box(s,54,158,1160,1,CARD);t(s,54,687,1150,21,'C项　多站中断、排名验证与参数敏感性　2026年11月 草稿',12,MUTED);
 if(a.chart){box(s,54,190,850,460,CARD);s.images.add({blob:new Uint8Array(await fs.readFile(input.base+'/results/figures/c/deck/'+a.chart)),contentType:'image/png',position:{left:64,top:197,width:830,height:448},fit:'contain'});t(s,935,215,285,430,a.take,24,GOLD,true);}
 if(a.text){a.text.forEach((r,j)=>{box(s,54,195+j*145,1160,123,CARD);t(s,78,213+j*145,320,38,r[0],26,TEAL,true);t(s,420,213+j*145,760,85,r[1],25);});}
 if(a.stats){a.stats.forEach((r,j)=>card(s,54+j*394,202,370,156,r[0],r[1]));t(s,70,405,1120,235,a.body,28,WHITE);}
 if(a.table){const xs=[70,350,950],ws=[280,600,250];a.table.forEach((row,j)=>{box(s,54,190+j*57,1160,54,j===0?'#1b4652':CARD);row.forEach((v,k)=>t(s,xs[k],202+j*57,ws[k]-20,38,v,j===0?21:23,j===0?TEAL:WHITE,j===0));});t(s,70,610,1130,68,a.body,22,GOLD);}
 }
 s.speakerNotes.text=a.note;
}
return {total:presentation.slides.items.length};}
