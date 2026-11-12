
from pathlib import Path
import csv

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据保存位置
DATA_DIR = BASE_DIR / "data"

# 如果文件夹不存在，就自动创建
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("项目目录：", BASE_DIR)
print("数据目录：", DATA_DIR)
print("准备完成！")

# S1线试乘开放站点（2026年11月12日）
s1_stations = [
    "省中医院西区",
    "合肥西站",
    "庐州公园",
    "大杨",
    "岗集",
    "未来大科学城",
    "长兴湖",
    "未来湖",
    "迎宾大道",
    "新桥2号航站楼"
]

# 保存为CSV文件
file_path = DATA_DIR / "s1_stations.csv"

with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["line", "sequence", "station", "status"])

    for i, station in enumerate(s1_stations, start=1):
        writer.writerow(["S1", i, station, "trial"])

print(f"S1线数据已保存：{file_path}")
print(f"共记录 {len(s1_stations)} 个站点")

# 合肥轨道交通1号线站点
line1_stations = [
    "九联圩", "丙子铺", "万年埠", "万达城",
    "云谷路", "金斗公园", "塘西河公园",
    "紫庐", "滨湖会展中心", "高王",
    "骆岗", "南站南广场", "合肥南站",
    "望湖城", "葛大店", "秋浦河路",
    "朱岗", "合工大南区", "包公园",
    "大东门", "明光路", "长淮",
    "合肥火车站", "瑶海公园",
    "兴华苑", "张洼"
]

# 保存1号线站点数据
file_path = DATA_DIR / "line1_stations.csv"

with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["line", "sequence", "station", "status"])

    for i, station in enumerate(line1_stations, start=1):
        writer.writerow(["1", i, station, "operating"])

print(f"1号线数据已保存：{file_path}")
print(f"1号线共记录 {len(line1_stations)} 个站点")

# 合肥轨道交通2号线站点
line2_stations = [
    "南岗", "桂庄", "汽车西站", "振兴路",
    "蜀山西", "大蜀山", "天柱路", "科学大道",
    "十里庙", "西七里塘", "五里墩", "三里庵",
    "安农大", "三孝口", "四牌楼", "大东门",
    "三里街", "东五里井", "东七里", "漕冲",
    "东二十埠", "龙岗", "王岗", "三十埠",
    "三十埠东", "祥和", "桂王", "对河",
    "店埠河", "排头", "肥东站", "和睦湖",
    "马桥", "南沙河", "撮镇"
]

# 通用函数：保存任意线路的数据
def save_line(line_name, stations):
    file_path = DATA_DIR / f"line{line_name}_stations.csv"

    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["line", "sequence", "station", "status"])

        for i, station in enumerate(stations, start=1):
            writer.writerow([line_name, i, station, "operating"])

    print(f"{line_name}号线：{len(stations)}站，保存成功！")

# 保存2号线
save_line("2", line2_stations)

# 合肥轨道交通3号线站点
line3_stations = [
    "相城路", "职教城东", "职教城", "幼儿师范",
    "文浍苑", "勤劳村", "新海大道", "窦桥湾",
    "方庙", "竹丝滩", "合肥火车站", "鸭林冲",
    "淮南路", "一里井", "海棠", "郑河",
    "四泉桥", "杏花村", "合肥西站", "南新庄",
    "西七里塘", "国防科技大学", "洪岗",
    "市政务中心", "合肥大剧院", "图书馆",
    "省博物院", "安医大二附院", "繁华大道",
    "大学城北", "工大翡翠湖校区",
    "安大磬苑校区", "幸福坝", "安医一附院南区",
    "凉亭", "李湾", "四十埠", "芮祠",
    "乐平", "省儿童医院新区"
]

# 调用之前定义的通用函数
save_line("3", line3_stations)

# 合肥轨道交通4号线（2026年运营线路）
line4_stations = [
    "综保区", "安医一附院北区", "陶冲湖东",
    "十里村", "新海公园", "方庙",
    "站塘", "东七里", "唐桥",
    "五里庙", "尧渡河路", "工经学院",
    "葛大店南", "望湖城南", "合肥南站",
    "淝南", "竹西", "薛河",
    "南屏路", "姚公庙", "天鹅湖东",
    "天鹅湖", "图书馆", "柳树塘",
    "金桂", "玉兰大道", "北雁湖",
    "复兴集", "长安集", "桃花潭",
    "金小郢", "铜锣寨路", "魏庄",
    "烧脉岗"
]

# 保存4号线数据
save_line("4", line4_stations)

# 合肥轨道交通5号线站点
line5_stations = [
    "汲桥路", "六中菱湖校区", "菱湖公园",
    "北五里井", "海棠", "白水坝",
    "杏花公园", "三孝口", "稻香楼",
    "中国科大东区", "市第三医院", "休宁路",
    "凌大塘", "望湖城西", "合肥南站",
    "盛大", "包河苑", "义兴",
    "大连路", "花园大道", "黄河路",
    "扬子江路", "义城", "省行政中心东",
    "方兴湖", "渡江纪念馆", "沈湾",
    "华山路", "云谷路", "清水冲",
    "云川公园", "滨湖竹园", "贵阳路"
]

# 使用之前定义的通用函数
save_line("5", line5_stations)

# 合肥轨道交通6号线运营站点
line6_stations = [
    "青龙岗", "合肥七中", "量子科学中心",
    "科大先研院", "北雁湖", "开福寺",
    "梦城", "松荫桥", "洪岗",
    "陆军兵种大学", "南七里",
    "市第三医院", "卫岗", "朱岗",
    "尧渡河路", "唐大楼", "市儿童医院",
    "钢红", "大兴集", "伏龙", "龙塘"
]

# 保存6号线运营站点
save_line("6", line6_stations)

# 合肥轨道交通7号线（2026年7月开通）
line7_stations = [
    "翡翠公园",
    "繁华大道",
    "徽园",
    "明珠广场",
    "天都路",
    "南艳湖北",
    "一六八中学",
    "合肥大学",
    "南艳湖南",
    "要素大市场",
    "滨湖医院",
    "紫庐",
    "嵩山路",
    "省文化和非遗馆"
]

# 保存7号线运营站点
save_line("7", line7_stations)

# 合肥轨道交通8号线一期站点
line8_stations = [
    "一里井",
    "杏林",
    "庐阳经开区",
    "六中菱湖校区",
    "荷塘路",
    "双凤",
    "金梅路",
    "梅冲湖",
    "北城世纪城",
    "双墩",
    "省立医院北区",
    "北城高铁站"
]

# 保存8号线数据
save_line("8", line8_stations)
