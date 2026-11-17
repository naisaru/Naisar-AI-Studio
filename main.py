import sys, os, json, time, secrets, shutil
from pathlib import Path
import requests
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QComboBox, QListWidget, QListWidgetItem, QFileDialog, QStackedWidget, QSpinBox, QDoubleSpinBox, QMessageBox

ROOT=Path(os.getenv("LOCALAPPDATA",str(Path.home()))) / "NaisarAIStudio"
CHECK=ROOT/"models"/"checkpoints"
LORA=ROOT/"models"/"loras"
GALLERY=ROOT/"gallery"
CONFIG=ROOT/"settings.json"
for p in (CHECK,LORA,GALLERY): p.mkdir(parents=True,exist_ok=True)

STYLE="""
QWidget{background:#12131a;color:#e9e8f1;font-family:'Segoe UI';font-size:13px}
QFrame#side{background:#1a1b24;border-right:1px solid #333443}
QLabel#title{font-size:23px;font-weight:700}
QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QListWidget{background:#252631;border:1px solid #424353;border-radius:9px;padding:8px}
QPushButton{background:#292a38;border:0;border-radius:9px;padding:11px}
QPushButton:hover{background:#38394b}
QPushButton#primary{background:#745ce0;font-weight:600}
QPushButton#nav{text-align:left;background:transparent}
QPushButton#nav:checked{background:#34304e}
"""
class Worker(QThread):
    done=Signal(str)
    failed=Signal(str)
    progress=Signal(str)
    def __init__(self,url,ckpt,pos,neg,w,h,steps,cfg,seed,loras):
        super().__init__()
        self.url,self.ckpt,self.pos,self.neg=url.rstrip('/'),ckpt,pos,neg
        self.w,self.h,self.steps,self.cfg,self.seed,self.loras=w,h,steps,cfg,seed,loras
    def run(self):
        try:
            nodes={
             "1":{"class_type":"CheckpointLoaderSimple","inputs":{"ckpt_name":self.ckpt}},
             "2":{"class_type":"CLIPTextEncode","inputs":{"text":self.pos,"clip":["1",1]}},
             "3":{"class_type":"CLIPTextEncode","inputs":{"text":self.neg,"clip":["1",1]}},
             "4":{"class_type":"EmptyLatentImage","inputs":{"width":self.w,"height":self.h,"batch_size":1}},
             "5":{"class_type":"KSampler","inputs":{"seed":self.seed,"steps":self.steps,"cfg":self.cfg,"sampler_name":"euler","scheduler":"normal","denoise":1.0,"model":["1",0],"positive":["2",0],"negative":["3",0],"latent_image":["4",0]}},
             "6":{"class_type":"VAEDecode","inputs":{"samples":["5",0],"vae":["1",2]}},
             "7":{"class_type":"SaveImage","inputs":{"filename_prefix":"Naisar","images":["6",0]}}}
            model,clip=["1",0],["1",1]
            for idx,(name,strength) in enumerate(self.loras,8):
                key=str(idx)
                nodes[key]={"class_type":"LoraLoader","inputs":{"lora_name":name,"strength_model":strength,"strength_clip":strength,"model":model,"clip":clip}}
                model,clip=[key,0],[key,1]
            nodes["2"]["inputs"]["clip"]=clip
            nodes["3"]["inputs"]["clip"]=clip
            nodes["5"]["inputs"]["model"]=model
            self.progress.emit("Отправка задачи в ComfyUI...")
            resp=requests.post(self.url+"/prompt",json={"prompt":nodes},timeout=20)
            resp.raise_for_status()
            data=resp.json()
            if "error" in data: raise RuntimeError(str(data["error"]))
            pid=data["prompt_id"]
            for _ in range(360):
                time.sleep(2)
                r=requests.get(self.url+"/history/"+pid,timeout=10)
                r.raise_for_status()
                history=r.json().get(pid)
                if history is None:
                    self.progress.emit("Генерация...")
                    continue
                if history.get("status",{}).get("status_str")=="error": raise RuntimeError("ComfyUI завершил задачу с ошибкой")
                images=history.get("outputs",{}).get("7",{}).get("images",[])
                if not images: raise RuntimeError("Изображение не найдено в ответе ComfyUI")
                info=images[0]
                image=requests.get(self.url+"/view",params={"filename":info["filename"],"subfolder":info.get("subfolder",""),"type":info.get("type","output")},timeout=40)
                image.raise_for_status()
                path=GALLERY/(str(int(time.time()*1000))+".png")
                path.write_bytes(image.content)
                path.with_suffix(".json").write_text(json.dumps({"prompt":self.pos,"negative":self.neg,"checkpoint":self.ckpt,"loras":self.loras,"seed":self.seed},ensure_ascii=False,indent=2),encoding="utf8")
                self.done.emit(str(path))
                return
            raise TimeoutError("Превышено время ожидания ComfyUI")
        except Exception as exc: self.failed.emit(str(exc))

class Studio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config={"url":"http://127.0.0.1:8188","checkpoints":"","loras":""}
        if CONFIG.exists():
            try:self.config.update(json.loads(CONFIG.read_text(encoding="utf8")))
            except (ValueError,OSError): pass
        self.setWindowTitle("Naisar AI Studio")
        self.resize(1200,780)
        self.setMinimumSize(900,600)
        center=QWidget();self.setCentralWidget(center)
        outer=QHBoxLayout(center);outer.setContentsMargins(0,0,0,0)
        sidebar=QFrame(objectName="side");sidebar.setFixedWidth(190)
        side=QVBoxLayout(sidebar)
        side.addWidget(QLabel("◈  NAISAR AI",objectName="title"))
        side.addSpacing(25)
        self.stack=QStackedWidget();self.nav=[]
        for i,(label,page) in enumerate((("✦  Генерация",self.generation_page),("▧  Галерея",self.gallery_page),("▤  Модели и LoRA",self.models_page),("⚙  Настройки",self.settings_page))):
            btn=QPushButton(label,objectName="nav");btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False,n=i:self.navigate(n))
            side.addWidget(btn);self.nav.append(btn)
            self.stack.addWidget(page())
        side.addStretch()
        outer.addWidget(sidebar);outer.addWidget(self.stack,1)
        self.navigate(0);self.refresh()
    def navigate(self,index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav):b.setChecked(i==index)
        if index==1:self.show_gallery()
        if index==2:self.refresh()
    def page(self,title):
        w=QWidget();lay=QVBoxLayout(w);lay.setContentsMargins(25,25,25,25);lay.setSpacing(12)
        lay.addWidget(QLabel(title,objectName="title"))
        return w,lay
    def generation_page(self):
        w,l=self.page("Создать изображение")
        l.addWidget(QLabel("Checkpoint"))
        self.ckpt=QComboBox();l.addWidget(self.ckpt)
        l.addWidget(QLabel("Промпт"))
        self.prompt=QTextEdit();self.prompt.setPlaceholderText("Опиши изображение...");self.prompt.setMaximumHeight(125);l.addWidget(self.prompt)
        l.addWidget(QLabel("Негативный промпт"))
        self.negative=QLineEdit("blurry, low quality, bad anatomy");l.addWidget(self.negative)
        l.addWidget(QLabel("LoRA (отметь нужные, сила 0.75)"))
        self.lora_list=QListWidget();self.lora_list.setMaximumHeight(120);l.addWidget(self.lora_list)
        options=QHBoxLayout()
        self.width=QSpinBox();self.width.setRange(256,1024);self.width.setSingleStep(64);self.width.setValue(512)
        self.height=QSpinBox();self.height.setRange(256,1024);self.height.setSingleStep(64);self.height.setValue(512)
        self.steps=QSpinBox();self.steps.setRange(1,150);self.steps.setValue(20)
        self.cfg=QDoubleSpinBox();self.cfg.setRange(1,30);self.cfg.setValue(7)
        self.seed=QSpinBox();self.seed.setRange(-1,2147483647);self.seed.setValue(-1)
        for name,field in (("Ширина",self.width),("Высота",self.height),("Steps",self.steps),("CFG",self.cfg),("Seed (-1 случайный)",self.seed)):
            v=QVBoxLayout();v.addWidget(QLabel(name));v.addWidget(field);options.addLayout(v)
        l.addLayout(options)
        self.runbtn=QPushButton("✦  Генерировать",objectName="primary");self.runbtn.clicked.connect(self.generate);l.addWidget(self.runbtn)
        self.status=QLabel("Необходимо запустить ComfyUI локально и выбрать checkpoint.");l.addWidget(self.status)
        self.preview=QLabel("Результат генерации");self.preview.setAlignment(Qt.AlignCenter);l.addWidget(self.preview,1)
        return w
    def gallery_page(self):
        w,l=self.page("Галерея")
        b=QPushButton("Открыть папку с изображениями");b.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(GALLERY))));l.addWidget(b)
        self.gallery=QListWidget();self.gallery.itemDoubleClicked.connect(lambda item:QDesktopServices.openUrl(QUrl.fromLocalFile(item.data(Qt.UserRole))));l.addWidget(self.gallery)
        l.addWidget(QLabel("Дважды нажми на изображение для открытия."))
        return w
    def models_page(self):
        w,l=self.page("Модели и LoRA")
        l.addWidget(QLabel("Импорт скачанных .safetensors (в том числе с Civitai.red)"))
        for title,is_lora in (("Добавить checkpoint",False),("Добавить LoRA",True)):
            b=QPushButton(title,objectName="primary");b.clicked.connect(lambda checked=False,x=is_lora:self.import_files(x));l.addWidget(b)
        self.models=QListWidget();l.addWidget(QLabel("Checkpoint"));l.addWidget(self.models)
        self.loras=QListWidget();l.addWidget(QLabel("LoRA"));l.addWidget(self.loras)
        l.addWidget(QLabel("Прямая загрузка с Civitai.red пока не реализована."))
        return w
    def settings_page(self):
        w,l=self.page("Настройки")
        l.addWidget(QLabel("Локальный адрес ComfyUI"))
        self.url=QLineEdit(self.config["url"]);l.addWidget(self.url)
        l.addWidget(QLabel("Папка ComfyUI/models/checkpoints"))
        self.check_folder=QLineEdit(self.config["checkpoints"]);l.addWidget(self.check_folder)
        l.addWidget(QLabel("Папка ComfyUI/models/loras"))
        self.lora_folder=QLineEdit(self.config["loras"]);l.addWidget(self.lora_folder)
        save=QPushButton("Сохранить",objectName="primary");save.clicked.connect(self.save);l.addWidget(save)
        test=QPushButton("Проверить ComfyUI");test.clicked.connect(self.test);l.addWidget(test)
        l.addStretch()
        return w
    def folder(self,is_lora):
        key="loras" if is_lora else "checkpoints"
        return Path(self.config[key]) if self.config[key] else (LORA if is_lora else CHECK)
    def refresh(self):
        models=sorted(p.name for p in self.folder(False).glob("*.safetensors"))
        loras=sorted(p.name for p in self.folder(True).glob("*.safetensors"))
        self.ckpt.clear();self.ckpt.addItems(models)
        self.models.clear();self.models.addItems(models)
        self.loras.clear();self.loras.addItems(loras)
        self.lora_list.clear()
        for name in loras:
            item=QListWidgetItem(name)
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.lora_list.addItem(item)
    def import_files(self,is_lora):
        paths,_=QFileDialog.getOpenFileNames(self,"Импорт моделей","","Safetensors (*.safetensors)")
        if not paths:
            return
        key="loras" if is_lora else "checkpoints"
        dest_name=QFileDialog.getExistingDirectory(self,"Выбери папку хранения моделей (желательно папку ComfyUI/models/"+key+")",str(self.folder(is_lora)))
        if not dest_name:
            return
        dest=Path(dest_name)
        try:
            dest.mkdir(parents=True,exist_ok=True)
            copied=0
            for path in paths:
                src=Path(path)
                target=dest/src.name
                if src.resolve()==target.resolve() or target.exists():
                    continue
                needed=src.stat().st_size+256*1024*1024
                free=shutil.disk_usage(dest).free
                if free<needed:
                    raise OSError("Недостаточно свободного места в "+str(dest)+". Необходимо примерно "+f"{needed/1024**3:.1f}"+" ГБ, доступно "+f"{free/1024**3:.1f}"+" ГБ.")
                try:
                    with src.open("rb") as source, target.open("xb") as output:
                        shutil.copyfileobj(source,output,4*1024*1024)
                except OSError:
                    target.unlink(missing_ok=True)
                    raise
                copied+=1
            self.config[key]=str(dest)
            CONFIG.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding="utf8")
            (self.lora_folder if is_lora else self.check_folder).setText(str(dest))
            self.refresh()
            QMessageBox.information(self,"Импорт","Импортировано файлов: "+str(copied)+"\\nПапка: "+str(dest)+"\\nЕсли ComfyUI использует другую папку, он не увидит модели.")
        except OSError as exc:
            QMessageBox.warning(self,"Ошибка импорта",str(exc)+"\\nВыбери папку на диске с большим количеством свободного места.")
    def save(self):
        self.config.update(url=self.url.text().strip(),checkpoints=self.check_folder.text().strip(),loras=self.lora_folder.text().strip())
        CONFIG.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding="utf8")
        self.refresh();QMessageBox.information(self,"Naisar AI","Настройки сохранены")
    def test(self):
        address=self.url.text().strip().rstrip("/")
        try:
            r=requests.get(address+"/system_stats",timeout=4)
            r.raise_for_status()
            QMessageBox.information(self,"ComfyUI","Соединение установлено. ComfyUI доступен.")
        except requests.RequestException:
            QMessageBox.warning(self,"ComfyUI не запущен","Невозможно подключиться к "+address+".\\n\\nЗапусти ComfyUI локально, дождись сообщения о запуске сервера и нажми «Проверить ComfyUI» снова.\\n\\nComfyUI не входит в установщик Naisar AI Studio v0.1.")
    def generate(self):
        if not self.ckpt.currentText() or not self.prompt.toPlainText().strip():
            QMessageBox.warning(self,"Генерация","Выбери checkpoint и введи промпт");return
        loras=[(self.lora_list.item(i).text(),0.75) for i in range(self.lora_list.count()) if self.lora_list.item(i).checkState()==Qt.Checked]
        seed=self.seed.value() if self.seed.value()>=0 else secrets.randbelow(2147483647)
        self.worker=Worker(self.config["url"],self.ckpt.currentText(),self.prompt.toPlainText(),self.negative.text(),self.width.value(),self.height.value(),self.steps.value(),self.cfg.value(),seed,loras)
        self.worker.done.connect(self.completed);self.worker.failed.connect(self.failed);self.worker.progress.connect(self.status.setText)
        self.runbtn.setEnabled(False);self.worker.start()
    def completed(self,path):
        self.runbtn.setEnabled(True);self.status.setText("Сохранено: "+path)
        pix=QPixmap(path);self.preview.setPixmap(pix.scaled(520,320,Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def failed(self,msg):
        self.runbtn.setEnabled(True)
        if "10061" in msg or "Connection refused" in msg or "Failed to establish a new connection" in msg or "Max retries exceeded" in msg:
            message="Локальный движок ComfyUI недоступен.\\n\\n1. Установи и запусти ComfyUI.\\n2. Дождись запуска сервера на 127.0.0.1:8188.\\n3. Проверь адрес в разделе «Настройки».\\n4. Нажми «Проверить ComfyUI» и повтори генерацию.\\n\\nОбрати внимание: ComfyUI не входит в текущий установщик Naisar AI Studio."
        else:
            message=msg
        self.status.setText("Ошибка генерации: "+message.split("\\n")[0])
        QMessageBox.warning(self,"Ошибка генерации",message)
    def show_gallery(self):
        self.gallery.clear()
        for path in sorted(GALLERY.glob("*.png"),key=lambda p:p.stat().st_mtime,reverse=True):
            item=QListWidgetItem(path.name);item.setData(Qt.UserRole,str(path));self.gallery.addItem(item)

def main():
    app=QApplication(sys.argv);app.setStyleSheet(STYLE)
    window=Studio();window.show();sys.exit(app.exec())
if __name__=="__main__":main()
