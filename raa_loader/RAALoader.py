# -*- coding: utf-8 -*-
# Andrew Mercer
# mercerraa@gmail.com
# Riksantikvarieämbetets handläggarstöd
# This version: 07.05.2026
from datetime import (
  datetime,
  timedelta
)
import os
import time
import uuid
#
from qgis.core import (
  Qgis,
  QgsAttributeEditorField,
  QgsAttributeEditorRelation,
  QgsDataSourceUri,
  QgsLayerTreeGroup,
  QgsLayerTreeLayer,
  QgsMessageLog,
  QgsNetworkAccessManager,
  QgsProject,
  QgsRelation,
  QgsVectorLayer,
)
from qgis.utils import iface
from qgis.gui import (
   QgsMapToolIdentifyFeature,
 )
from qgis.PyQt.QtCore import (
  pyqtSignal,
  QFile,
  QIODevice,
  QObject,
  Qt,
  QUrl,
)
from qgis.PyQt.QtWidgets import (
  QDialog,
  QFileDialog,
  QLabel,
  QMessageBox,
  QProgressBar,
  QPushButton,
  QTreeWidget,
  QTreeWidgetItem,
  QVBoxLayout,
)
from qgis.PyQt.QtNetwork import( 
  QNetworkRequest,
  QNetworkReply
)

###########################
#
messageText = f'**** Reloaded {datetime.now()} ****\n'
QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
thisDir = os.path.dirname(os.path.realpath(os.path.expanduser(__file__)))
symbDir = os.path.join(thisDir, 'Symbology')
placeKomb = "Kombinerad" # Name used by >1 functions for identification
#
def messageOut(title, messageText, level = Qgis.Info, duration = 3):
  """Sends message to user via QGIS message bar and to the built in QGIS Python console.
  Levels are Qgis.Info, Qgis.Warning, Qgis.Critical, Qgis.Success
  More of a convenience as it has defaults set. Also prints to python console."""
  QgsMessageLog.logMessage(messageText, 'RAÄ', level)
  iface.messageBar().pushMessage(title, messageText, level, duration)
#
def setInitialPath(dataFolder='InData'):
  """Get path for data for current project"""
  # Define and set names and paths
  projectInstance = QgsProject.instance()
  projectPath = projectInstance.absolutePath()
  currentDir = os.getcwd()
  #
  if projectPath != currentDir and projectPath != '':
    os.chdir(os.path.normpath(projectPath))
    currentDir = os.getcwd()
  # Set path for directory window to start in 
  datasetDir = os.path.join(currentDir, dataFolder)
  if os.path.exists(datasetDir):
    defaultDir = datasetDir
  else:
    defaultDir = currentDir
  inDir = getFolder(defaultDir, "Välj projektets datamapp")
  if inDir == "" or inDir == None:
    return None
  if not os.path.exists(inDir):
    try:
      inDir = os.path.join(projectPath, dataFolder)
      if not os.path.exists(inDir):
        os.makedirs(inDir)
    except:
      messageOut('ERROR!','Ingen giltig mapp angiven', Qgis.Critical, 10)
      return None
  return inDir
#
def getFolder(startpath, prompt = "Välj mapp"):
  """Asks user to select a directory for use with project"""
  try:
    folder = QFileDialog.getExistingDirectory(
    None,
    prompt,
    startpath,
    QFileDialog.ShowDirsOnly
    )
  except:
    folder = QFileDialog.getExistingDirectory(
    None,
    prompt,
    startpath,
    QFileDialog.Option.ShowDirsOnly
    )
  if folder:
    return folder
  else:
    return None
#
def replaceString(filePath, oldStr, newStr):
  """Search through text file and replace text."""
  with open(filePath, 'r') as file:
    filedata = file.read()
  filedata = filedata.replace(oldStr, newStr)
  with open(filePath, 'w') as file:
    file.write(filedata)
  return
#
def deSwede(str):
  """Removes Swedish, non-ascii letters"""
  letters = [ ['Å','A'], ['å','a'], ['Ä','A'], ['ä','a'],['Ö','O'], ['ö','o']]
  for pair in letters:
    str = str.replace(pair[0], pair[1])
  return str
#
def deClutter(str, deSwe=True):
  """Remove characters not compatible with older naming conventions"""
  if deSwe:
    str = deSwede(str)
  characters = [[',',''], ['.',''], [' ','_'], [':','_'], ['?',''], ['!',''], ['"',''], ['*',''], ['#',''], ['%',''], ['&','A'], ['/','_'], ['\\','_']]
  for pair in characters:
    str = str.replace(pair[0], pair[1])
  return str
#
def getFileTime(path):
  """Gets creation and update time stamps of a file."""
  # elapsed since EPOCH in float
  ti_c = os.path.getctime(path) # Created
  ti_m = os.path.getmtime(path) # Modified
  # Converting the time in seconds to a timestamp
  c_ti = time.ctime(ti_c) # Created
  m_ti = time.ctime(ti_m) # Modified
  return {'createSeconds':ti_c, 'modifySeconds':ti_m, 'createTime':c_ti, 'modifyTime':m_ti}
#
def progressDisplay(message = "Ladda ner filer"):
  """Creates a progress bar to give some feedback to user during long processes. """
  progressMessageBar = iface.messageBar().createMessage(message)
  progress = QProgressBar()
  progress.setMaximum(100)
  try: ### Qt5
    progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
  except: ### Qt6
    progress.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
  progressMessageBar.layout().addWidget(progress)
  iface.messageBar().pushWidget(progressMessageBar, Qgis.Info)
  return progress, progressMessageBar
#
class responseDialog(QDialog):
  """Convenience for getting OK from user.
  Usage:
  def getResponse():
    dlg = responseDialog("Title","Message text", iface.mainWindow())
    if dlg.exec():
      print('OK pressed') # Or something more useful
    return
  """
  def __init__(self, titleText, message1, message2 = "", parent = None):
    super().__init__(parent)
    charcount = len(message1)
    width = 110 + charcount*1
    self.resize(width, 75)
    self.setWindowTitle(titleText)
    layout = QVBoxLayout()
    layout.addWidget(QLabel(message1))
    if not message2 == "":
      layout.addWidget(QLabel(message2))
    self.ok_button = QPushButton("OK")
    self.cancel_button = QPushButton("Cancel")
    self.ok_button.clicked.connect(self.accept)
    self.cancel_button.clicked.connect(self.reject)
    layout.addWidget(self.ok_button)
    layout.addWidget(self.cancel_button)
    self.setLayout(layout)
    messageText  = f"{titleText}: {message1} - {message2}"
    QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
#
def messagify(dictionary):
  """Takes a dictionary and returns a string of contents for feedback to debug or log."""
  string = '- - - - From dictionary: '
  for name, content in dictionary.items():
    string += f'{name}: {content} \n'
  return string
#
def downloadCheck(filePath, upfrq=2):
  """Does a source file need updating? This function checks the modification date of a file against the current date. 
  If the difference is greater than the specified update frequency check for a new source data file"""
  down = False # Do not download the file
  if os.path.isfile(filePath): # Does the file even exist?
    todaydt = datetime.now()
    today = todaydt.date()
    if os.path.getsize(filePath) > 0: # Did a previous download fail? Not full check
      fileTimeStamp = getFileTime(filePath)
      filedt = datetime.strptime(fileTimeStamp['modifyTime'], "%a %b %d %H:%M:%S %Y")
      diffDT = today - filedt.date()
      if (diffDT) > timedelta(upfrq): # Is the file out of date?
        title = "Filen finns redan"
        message1 = f"{filePath} är endast {diffDT} dagar gammal"
        message2 = "Tryck OK för att ladda ner ändå"
        dlg = responseDialog(title, message1, message2, iface.mainWindow())
        if dlg.exec():
          down = True # Do download the file as existing is too old
        else:
          down = False
  else:
    down = True # Do download the file as none found
  #print(f'downloadCheck: need to download {filePath} = {down}')
  return down
#
class DownloadManager(QObject):
  """Replaces download_url() which used requests.
  Uses QgsNetworkAccessManager to manage downloads and passing finished downloads on for further processing.
  """
  jobFinished = pyqtSignal(str, str, object)  
  # (url, file_path, result)
  jobFailed = pyqtSignal(str, str, str)  
  # (url, file_path, error_string)
  progressChanged = pyqtSignal(str, int)  
  # (url, percent)
  allFinished = pyqtSignal()
  def __init__(self, parent=None, max_parallel=3):
    super().__init__(parent)
    self.max_parallel = max_parallel
    self.queue = []
    self.active = 0
    self.active_replies = {}
    self.is_cancelled = False
  def add_job(self, url, file_path, callback, dummy=None):
    messageText = f'DownloadManager: {url} --> {file_path}'
    QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
    self.queue.append({
      "url": url,
      "path": file_path,
      "dummy": dummy,
      "callback": callback
    })
  def start(self):
    for _ in range(self.max_parallel):
      self._start_next()
  def cancel_all(self):
    self.is_cancelled = True
    self.queue.clear()
    for reply in list(self.active_replies.values()):
      reply.abort()
    self.active_replies.clear()
    self.allFinished.emit()
  def _start_next(self):
    if self.is_cancelled:
      return
    if not self.queue and self.active == 0:
      self.allFinished.emit()
      return
    if not self.queue or self.active >= self.max_parallel:
      return
    job = self.queue.pop(0)
    self.active += 1
    self._download(job)
  def _download(self, job):
    nam = QgsNetworkAccessManager.instance()
    request = QNetworkRequest(QUrl(job["url"]))
    reply = nam.get(request)
    job_id = id(job)
    self.active_replies[job_id] = reply
    file_handle = QFile(job["path"])
    try:
      if not file_handle.open(QIODevice.WriteOnly):
        self._fail(job, "Could not open file for writing")
        return
    except:
      if not file_handle.open(QIODevice.OpenModeFlag.WriteOnly):
        self._fail(job, "Could not open file for writing")
        return
    # ---- WRITE DATA ----
    def on_ready_read():
      file_handle.write(reply.readAll())
    # ---- PROGRESS ----
    def on_progress(received, total):
      if total > 0:
        percent = int((received / total) * 100)
        self.progressChanged.emit(job["url"], percent)
    # ---- FINISHED ----
    def on_finished():
      messageText = f"Download {job_id} complete"
      QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
      if job_id in self.active_replies:
        del self.active_replies[job_id]
      file_handle.flush()
      file_handle.close()
      reply.deleteLater()
      try:
        errorCheck = QNetworkReply.NoError
      except:
        errorCheck = reply.NetworkError.NoError
      if reply.error() == errorCheck:
        try:
          result = job["callback"](job["url"], job["path"], job["dummy"])
          self.jobFinished.emit(job["url"], job["path"], result)
        except Exception as e:
          self.jobFailed.emit(job["url"], job["path"], str(e))
      else:
        self.jobFailed.emit(
          job["url"],
          job["path"],
          reply.errorString()
        )
      self.active -= 1
      self._start_next()
    reply.readyRead.connect(on_ready_read)
    reply.downloadProgress.connect(on_progress)
    reply.finished.connect(on_finished)
  def _fail(self, job, message):
    self.jobFailed.emit(job["url"], job["path"], message)
    self.active -= 1
    self._start_next()
#
def saveStyle(layer):
  style_name = "Default RAA style"
  description = "Saved via PyQGIS"
  use_as_default = True
  ui_file_content = ""
  try:
    result = layer.saveStyleToDatabaseV2(
    style_name,
    description,
    use_as_default,
    ui_file_content
    )
    if not result[1] == '':
     messageText =f"saveStyle()V2: {layer.name()} {result}"
     QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  except:
    result = layer.saveStyleToDatabase(
      style_name,
      description,
      use_as_default,
      ui_file_content
      )
    if not result[1] == '':
      messageText = f"saveStyle(): {layer.name()} {result}"
      QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  return
#
class LansSelectorDialog(QDialog):
    DOWNLOAD_kommuner = "kommuner"
    DOWNLOAD_lan = "län"
    DOWNLOAD_land = "land"

    def __init__(self, lans_dict, found_dict, smallestRegion, instruction1, instruction2):
        super().__init__(iface.mainWindow())
        self.setWindowTitle(instruction1)
        self.resize(600, 600)
        self.lans_dict = lans_dict
        self.found_dict = found_dict
        self.download_mode = None
        self.smallestRegion = smallestRegion
        layout = QVBoxLayout()
        layout.addWidget(QLabel(instruction2))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Område"])
        layout.addWidget(self.tree)
        # --- ROOT: Sverige ---
        self.root_item = QTreeWidgetItem(["Sverige"])
        try: ### Qt5
          self.root_item.setFlags(self.root_item.flags() | Qt.ItemIsUserCheckable)
          self.root_item.setCheckState(0, Qt.Unchecked)
        except: ### Qt6
          self.root_item.setFlags(self.root_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
          self.root_item.setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.addTopLevelItem(self.root_item)
        self.tree.expandAll()
        # --- Populate tree ---
        for parent_name, children in self.lans_dict.items():
            parent_item = QTreeWidgetItem([parent_name])
            try: ### Qt5
              parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)
              parent_item.setCheckState(0, Qt.Unchecked)
            except: ### Qt6
              parent_item.setFlags(parent_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
              parent_item.setCheckState(0, Qt.CheckState.Unchecked)
            self.root_item.addChild(parent_item)

            for child_name in children:
                child_item = QTreeWidgetItem([child_name])
                try: ### Qt5
                  child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)
                  child_item.setCheckState(0, Qt.Unchecked)
                except: ### Qt6
                  child_item.setFlags(child_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                  child_item.setCheckState(0, Qt.CheckState.Unchecked)
                parent_item.addChild(child_item)
        #self.tree.expandAll()
        self.tree.itemChanged.connect(self.handle_item_changed)
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton("Cancel")
        layout.addWidget(btn_ok)
        layout.addWidget(btn_cancel)
        self.setLayout(layout)
        btn_ok.clicked.connect(self.handle_accept)
        btn_cancel.clicked.connect(self.reject)

    def handle_item_changed(self, item, column):
        if not item or column != 0:
            return
        self.tree.blockSignals(True)
        state = item.checkState(0)
        # --- Downward ---
        for i in range(item.childCount()):
            item.child(i).setCheckState(0, state)
        # --- Upward ---
        parent = item.parent()
        while parent:
            all_checked = True
            any_checked = False
            try: ### Qt5
              for i in range(parent.childCount()):
                  ch = parent.child(i)
                  if ch.checkState(0) != Qt.Checked:
                      all_checked = False
                  if ch.checkState(0) != Qt.Unchecked:
                      any_checked = True
              if all_checked:
                  parent.setCheckState(0, Qt.Checked)
              elif any_checked:
                  parent.setCheckState(0, Qt.PartiallyChecked)
              else:
                  parent.setCheckState(0, Qt.Unchecked) 
            except: ### Qt6
              for i in range(parent.childCount()):
                  ch = parent.child(i)
                  if ch.checkState(0) != Qt.CheckState.Checked:
                      all_checked = False
                  if ch.checkState(0) != Qt.CheckState.Unchecked:
                      any_checked = True
              if all_checked:
                  parent.setCheckState(0, Qt.CheckState.Checked)
              elif any_checked:
                  parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
              else:
                  parent.setCheckState(0, Qt.CheckState.Unchecked)
            parent = parent.parent()
        self.tree.blockSignals(False)

    def handle_accept(self):
      selection, downloadType = self.get_selected_dict()
      sverige_state = self.root_item.checkState(0)
      try: ### Qt5
        all_lan_selected = sverige_state == Qt.Checked
      except: ### Qt6
        all_lan_selected = sverige_state == Qt.CheckState.Checked
      all_kommuner_per_lan = self._all_kommuner_selected(selection)
      # --- CASE 1: Whole country ---
      btn_muni = None
      if all_lan_selected:
          msg = QMessageBox(self)
          msg.setWindowTitle("Hela Sverige valt")
          msg.setText("Hur vill du ladda ner data?")
          try: ### Qt5
            btn_country = msg.addButton("En fil för hela Sverige", QMessageBox.AcceptRole)
            btn_lan = msg.addButton("En fil per län", QMessageBox.AcceptRole)
            if self.smallestRegion == 'kommun':
              btn_muni = msg.addButton("En fil per kommun", QMessageBox.AcceptRole)
            msg.exec_()
          except: ### QT6
            btn_country = msg.addButton("En fil för hela Sverige", QMessageBox.ButtonRole.AcceptRole)
            btn_lan = msg.addButton("En fil per län", QMessageBox.ButtonRole.AcceptRole)
            if self.smallestRegion == 'kommun':
              btn_muni = msg.addButton("En fil per kommun", QMessageBox.ButtonRole.AcceptRole)
            msg.exec()
          if msg.clickedButton() == btn_country:
              self.download_mode = self.DOWNLOAD_land
          elif msg.clickedButton() == btn_lan:
              self.download_mode = self.DOWNLOAD_lan
          elif msg.clickedButton() == btn_muni:
              self.download_mode = self.DOWNLOAD_kommuner
          else:
              return
      # --- CASE 2: Full counties ---
      elif all_kommuner_per_lan and self.smallestRegion == 'kommun':
          msg = QMessageBox(self)
          msg.setWindowTitle("Hela län valt")
          msg.setText("Hur vill du ladda ner data?")
          try: ### Qt5
            btn_lan = msg.addButton("En fil per län", QMessageBox.AcceptRole)
            btn_muni = msg.addButton("En fil per kommun", QMessageBox.AcceptRole)
          except: ### Qt6
            btn_lan = msg.addButton("En fil per län", QMessageBox.ButtonRole.AcceptRole)
            btn_muni = msg.addButton("En fil per kommun", QMessageBox.ButtonRole.AcceptRole)
          try: ### Qt5
            msg.exec_()
          except: ### Qt6
            msg.exec()
          if msg.clickedButton() == btn_lan:
              self.download_mode = self.DOWNLOAD_lan
          else:
              self.download_mode = self.DOWNLOAD_kommuner
      elif all_kommuner_per_lan:
        self.download_mode = self.DOWNLOAD_lan
      else:
          self.download_mode = self.DOWNLOAD_kommuner
      self.accept()

    def _all_lan_selected(self, selection):
        """Check if all län are selected"""
        return len(selection) == len(self.lans_dict)
    
    def _all_kommuner_selected(self, selection):
      if not selection:
          return False
      for lan, kommuner in selection.items():
          if set(kommuner) != set(self.lans_dict[lan]):
              return False
      return True
    
    def get_selected_dict(self):
      selected = {}
      downloadMode = self.download_mode
      for i in range(self.root_item.childCount()):
          parent_item = self.root_item.child(i)
          parent_name = parent_item.text(0)
          parent_state = parent_item.checkState(0)
          # If whole lan checked → include ALL kommuner
          try: ### Qt5
             if parent_state == Qt.Checked: ### Qt5
              selected[parent_name] = list(self.lans_dict[parent_name])
              continue
          except: ### Qt6
            if parent_state == Qt.CheckState.Checked: ### Qt6
                selected[parent_name] = list(self.lans_dict[parent_name])
                continue
          selected_children = []
          for j in range(parent_item.childCount()):
              child_item = parent_item.child(j)
              try: ### Qt5
                if child_item.checkState(0) == Qt.Checked:
                  selected_children.append(child_item.text(0))
              except: ### Qt6
                if child_item.checkState(0) == Qt.CheckState.Checked:
                  selected_children.append(child_item.text(0))
          if selected_children:
              selected[parent_name] = selected_children
      return selected, downloadMode
#
def open_lans_selector(datasetName, smallestRegion="kommun", instruction1="Välj Sverige, län eller kommun", instruction2="Välj ett eller flera län/kommuner:"):
    """Creates a dialog window in QGIS that shows a checkbox list of all län and kommuner in Sweden
     and marks as checked those currently in the group chosen via datasetName"""
    try:
      found = getCurrentLayers(datasetName)
    except:
      return
      print("getCurrentLayers failed")
    try:
      lans = makeAreas()
    except:
      return
      
    try:
      dlg = LansSelectorDialog(lans, found, smallestRegion, instruction1, instruction2)
      try:
        dlgExec = dlg.exec_() ### Qt5
      except:
        dlgExec = dlg.exec() ### Qt6
      if dlgExec:
        selected_dict, downloadMode = dlg.get_selected_dict()
        # Display result as message
        if not selected_dict:
          QMessageBox.information(iface.mainWindow(), "Urval", "Avbrutet.")

        return selected_dict, downloadMode
    except:
      print("LansSelectorDialog failed")
      return
#
def makeAreas():
  """Dictionary of all of Sweden's län and kommuner. The order follows numerical codes for each län"""
  lans = {}
  lans['Stockholm'] = sorted(["Upplands Väsby" , "Vallentuna" , "Österåker" , "Värmdö" , "Järfälla" , "Ekerö" , "Huddinge" , "Botkyrka" , "Salem" , "Haninge" , "Tyresö" , "Upplands-Bro" , "Nykvarn" , "Täby" , "Danderyd" , "Sollentuna" , "Stockholm" , "Södertälje" , "Nacka" , "Sundbyberg" , "Solna" ,"Lidingö" , "Vaxholm" , "Norrtälje" , "Sigtuna" , "Nynäshamn"])
  lans['Uppsala'] = sorted(["Håbo" , "Älvkarleby" , "Knivsta" , "Heby" , "Tierp" , "Uppsala" , "Enköping" , "Östhammar"])
  lans['Södermanland'] = sorted(["Vingåker", "Gnesta", "Nyköping", "Oxelösund", "Flen", "Katrineholm", "Eskilstuna", "Strängnäs", "Trosa"])
  lans['Östergötland'] = sorted(["Ödeshög", "Ydre", "Kinda", "Boxholm", "Åtvidaberg", "Finspång", "Valdemarsvik", "Linköping", "Norrköping", "Söderköping", "Motala", "Vadstena", "Mjölby"])
  lans['Jönköping'] = sorted(["Aneby", "Gnosjö", "Mullsjö", "Habo", "Gislaved", "Vaggeryd", "Jönköping", "Nässjö", "Värnamo", "Sävsjö", "Vetlanda", "Eksjö", "Tranås"])
  lans['Kronoberg'] = sorted(["Uppvidinge", "Lessebo", "Tingsryd", "Alvesta", "Älmhult", "Markaryd", "Växjö", "Ljungby"])
  lans['Kalmar'] = sorted(["Högsby", "Torsås", "Mörbylånga", "Hultsfred", "Mönsterås", "Emmaboda", "Kalmar", "Nybro", "Oskarshamn", "Västervik", "Vimmerby", "Borgholm"])
  lans['Gotland'] = sorted(["Gotland"])
  lans['Blekinge'] = sorted(["Olofström", "Karlskrona", "Ronneby", "Karlshamn", "Sölvesborg"])
  lans['Skåne'] = sorted(["Svalöv", "Staffanstorp", "Burlöv", "Vellinge", "Östra Göinge", "Örkelljunga", "Bjuv", "Kävlinge", "Lomma", "Svedala", "Skurup", "Sjöbo", "Hörby", "Höör", "Tomelilla", "Bromölla", "Osby", "Perstorp", "Klippan", "Åstorp", "Båstad", "Malmö", "Lund", "Landskrona", "Helsingborg", "Höganäs", "Eslöv", "Ystad", "Trelleborg", "Kristianstad", "Simrishamn", "Ängelholm", "Hässleholm"])
  lans['Halland'] = sorted(["Hylte", "Halmstad", "Laholm", "Falkenberg", "Varberg", "Kungsbacka"])
  lans['Västra Götaland'] = sorted(["Härryda", "Partille", "Öckerö", "Stenungsund", "Tjörn", "Orust", "Sotenäs", "Munkedal", "Tanum", "Dals-Ed", "Färgelanda", "Ale", "Lerum", "Vårgårda", "Bollebygd", "Grästorp", "Essunga", "Karlsborg", "Gullspång", "Tranemo", "Bengtsfors", "Mellerud", "Lilla Edet", "Mark", "Svenljunga", "Herrljunga", "Vara", "Götene", "Tibro", "Töreboda", "Göteborg", "Mölndal", "Kungälv", "Lysekil", "Uddevalla", "Strömstad", "Vänersborg", "Trollhättan", "Alingsås", "Borås", "Ulricehamn", "Åmål", "Mariestad", "Lidköping", "Skara", "Skövde", "Hjo", "Tidaholm", "Falköping"])
  lans['Värmland'] = sorted(["Kil", "Eda", "Torsby", "Storfors", "Hammarö", "Munkfors", "Forshaga", "Grums", "Årjäng", "Sunne", "Karlstad", "Kristinehamn", "Filipstad", "Hagfors", "Arvika", "Säffle"])
  lans['Örebro'] = sorted(["Lekeberg", "Laxå", "Hallsberg", "Degerfors", "Hällefors", "Ljusnarsberg", "Örebro", "Kumla", "Askersund", "Karlskoga", "Nora", "Lindesberg"])
  lans['Västmanland'] = sorted(["Skinnskatteberg", "Surahammar", "Kungsör", "Hallstahammar", "Norberg", "Västerås", "Sala", "Fagersta", "Köping", "Arboga"])
  lans['Dalarna'] = sorted(["Vansbro", "Malung-Sälen", "Gagnef", "Leksand", "Rättvik", "Orsa", "Älvdalen", "Smedjebacken", "Mora", "Falun", "Borlänge", "Säter", "Hedemora", "Avesta", "Ludvika"])
  lans['Gävleborg'] = sorted(["Ockelbo", "Hofors", "Ovanåker", "Nordanstig", "Ljusdal", "Gävle", "Sandviken", "Söderhamn", "Bollnäs", "Hudiksvall"])
  lans['Västernorrland'] = sorted(["Ånge", "Timrå", "Härnösand", "Sundsvall", "Kramfors", "Sollefteå", "Örnsköldsvik"])
  lans['Jämtland'] = sorted(["Ragunda", "Bräcke", "Krokom", "Strömsund", "Åre", "Berg", "Härjedalen", "Östersund"])
  lans['Västerbotten'] = sorted(["Nordmaling", "Bjurholm", "Vindeln", "Robertsfors", "Norsjö", "Malå", "Storuman", "Sorsele", "Dorotea", "Vännäs", "Vilhelmina", "Åsele", "Umeå", "Lycksele", "Skellefteå"])
  lans['Norrbotten'] = sorted(["Arvidsjaur", "Arjeplog", "Jokkmokk", "Överkalix", "Kalix", "Övertorneå", "Pajala", "Gällivare", "Älvsbyn", "Luleå", "Piteå", "Boden", "Haparanda", "Kiruna"])
  return lans
#
# Project ToC
#
def getLayerSource(layer):
  """
  Return the actual dataset/layer name from the data source (GeoPackage, Shapefile, PostGIS, etc.)
  not the user-renamed display name.
  Courtesy of ChatGPT
  """
  try:
    source = layer.source()
  except:
     return False
  # --- GeoPackage ---
  if ".gpkg" in source.lower():
    parts = source.split("|")
    for p in parts:
        if p.startswith("layername="):
            return p.split("=", 1)[1]
    # fallback: use file name if not found
    return os.path.splitext(os.path.basename(parts[0]))[0]
  # --- PostGIS or other DB connection ---
  if "dbname=" in source or "table=" in source:
    uri = QgsDataSourceUri(source)
    tbl = uri.table()
    if tbl:
      return tbl
  # --- Shapefile / GeoJSON / File-based vector ---
  if source.lower().endswith((".shp", ".geojson", ".gml", ".sqlite")):
    return os.path.splitext(os.path.basename(source))[0]
  # --- Raster layer ---
  if layer.type() == layer.RasterLayer:
    return os.path.basename(source)
  # --- Fallback ---
  return layer.name()
#
def gpkgLayerPosition(sourcePackage, sourceLayer):
  """Pass the geopackage layer name, the part after '|layername=', and check if the layer already exists in the project ToC"""
  projectInstance = QgsProject.instance()
  root = projectInstance.layerTreeRoot()
  parent = False
  index = False
  layer = False
  # Get existing layer and its tree position
  sourceSplit = sourcePackage.split('/')
  packageLayer = sourceSplit[-1]
  packageName = packageLayer.split('|')[0]
  try:
    for layer in QgsProject.instance().mapLayers().values():
      if packageName in layer.source() and sourceLayer in layer.source():
        tree_layer = root.findLayer(layer.id())
        parent = tree_layer.parent()
        index = parent.children().index(tree_layer)
        break
      else:
        layer = False
  except:
    layer = False
  return layer, parent, index
#
def getCurrentLayers(datasetName = 'Lämningar'):
  '''Get dictionary of län and kommuner currently in project for dataset (lämningar/bebyggelse)'''
  projectInstance = QgsProject.instance()
  root = projectInstance.layerTreeRoot()
  lans = makeAreas()
  found = {}
  if root.findGroup(datasetName):
    datasetGroup = root.findGroup(datasetName)
    for lanName, kommuner in lans.items():
      if datasetGroup.findGroup(lanName):
        lanGroup = datasetGroup.findGroup(lanName)
        found[lanName] = []
        for kommun in kommuner:
          if lanGroup.findGroup(kommun):
            found[lanName].append(kommun)
  return found
#
def layerPosition(sourceLayer):
  '''Function takes a layer name and returns its parent and index in the layer tree
  parent, index = layerPosition(sourceLayer)'''
  projectInstance = QgsProject.instance()
  root = projectInstance.layerTreeRoot()
  parent = False
  index = False
  layer = False # Empty project -> for layer doesnt loop
  # Get existing layer and its tree position
  for layer in QgsProject.instance().mapLayers().values():
    if getLayerSource(layer) == sourceLayer:
      tree_layer = root.findLayer(layer.id())
      parent = tree_layer.parent()
      index = parent.children().index(tree_layer)
      break
    else:
      layer = False
  return layer, parent, index
#
def layersFromGroup(group):
  """Returns a list of layers in the provided group
  Args:
      node
  Returns:
      list of nodes
  """
  layers = []
  for child in group.children():
    if isinstance(child, QgsLayerTreeLayer):
      layers.append(child.layer())
    elif isinstance(child, QgsLayerTreeGroup):
      layers.extend(layersFromGroup(child))
  return layers
#
def selectedGroupLayers():
  """Returns a list of all the layers marked in the ToC"""
  treeView = iface.layerTreeView()
  selected_nodes = treeView.selectedNodes()
  allLayers = []
  for node in selected_nodes:
    if isinstance(node, QgsLayerTreeGroup):
      allLayers.extend(layersFromGroup(node))
    elif isinstance(node, QgsLayerTreeLayer):
      allLayers.append(node.layer())
  allLayers = list({layer.id(): layer for layer in allLayers}.values())
  layerNames = ',\n'.join([i.name() for i in allLayers])
  messageText = f'selectedGroupLayers: Valda lager:\n{layerNames}'
  QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  return allLayers
#
def findLayerByString(string1, string2 = ""):
  """Find layer by string of part of name)"""
  global placeKomb
  projectInstance = QgsProject.instance()
  layer = False # Empty project -> for layer doesnt loop
  for layer in QgsProject.instance().mapLayers().values():
    if string1.lower() in layer.source().lower() and string2.lower() in layer.source().lower():
      break
    elif string1 == placeKomb and string2.lower() in layer.source().lower():
      break
    else:
      layer = False
  return layer
#
def writeRelation(parentID, childID, parentField, childField, relName ):
  """Writes relation to project"""
  messageText = f"writeRelation: Attempting to create {relName}"
  QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  relID = str(uuid.uuid4())
  rel = QgsRelation()
  rel.setReferencingLayer( childID )
  rel.setReferencedLayer( parentID )
  rel.addFieldPair( childField, parentField )
  rel.setId( relID )
  rel.setName( relName )
  rel.setStrength(QgsRelation.Association) # QgsRelation.Composition or QgsRelation.Association
  relsInProj = QgsProject.instance().relationManager().relationsByName(relName)
  if rel.isValid() and len(relsInProj) == 0:
    QgsProject.instance().relationManager().addRelation( rel )
    messageText = f"writeRelation: Relation {relName} created with ID {relID}"
    QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
    return relID
  else:
    QgsMessageLog.logMessage(f'writeRelation: Failed on {relName}', 'RAÄ', level = Qgis.Info)
    return None
#
# Add layers to project
#
def gpkgLayerInsert(settings):
  """
  Insert geopackage layer to ToC. Will replace existing layer from same source.
  """
  sourcePackage = settings['geopackage']
  sourceLayer = settings['sourceLayer']
  layerName = settings['layerName']
  layerStyle = settings['layerStyle']
  oldLayer, parent, index = gpkgLayerPosition(sourcePackage, sourceLayer)
  if oldLayer:
    messageText = f"Old layer found: {oldLayer.name()}, {oldLayer.id()}"
    iface.setActiveLayer(oldLayer)
    iface.actionCopyLayerStyle().trigger()
    QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
    QgsProject.instance().removeMapLayer(oldLayer.id())
    #parent.removeLayer(oldLayer)
  elif oldLayer == False and settings['parent'] == False:
    root = QgsProject.instance().layerTreeRoot()
    try:
      if not root.findGroup(settings['groupName']):
        root.insertGroup(0,settings['groupName'])
      parent = root.findGroup(settings['groupName'])
      index = 0
    except:
      parent = root
      index = 0
  else:
    parent = settings['parent']
    index = 0
  newLayer = gpkgLayerAdd(sourcePackage, sourceLayer, layerName)
  newTreeLayer = QgsLayerTreeLayer(newLayer)
  parent.insertChildNode(index, newTreeLayer)
  if not layerStyle == '':
    newLayer.loadNamedStyle(layerStyle)
    saveStyle(newLayer)
  iface.setActiveLayer(newLayer)
  if layerStyle == '' and oldLayer:
    iface.actionPasteLayerStyle().trigger()
  layerNode = parent.findLayer(newLayer.id())
  if layerNode:
    layerNode.setExpanded(False)
  parent.setExpanded(False)
  messageText = f"gpkgLayerInsert: layer {newLayer.name()} added to ToC"
  QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  return
#
def gpkgLayerAdd(sourcePackage, sourceLayerName, layerName):
  '''Adds a layer from a geopackage to the QGIS project but doesn't insert it into the layer tree.
  Not inserting into layer tree is important here for updating an existing layer and putting back at same location in tree.'''
  layer = QgsVectorLayer(f"{sourcePackage}|layername={sourceLayerName}", layerName, "ogr")
  if not layer.isValid():
    raise Exception(f"Could not load layer: {sourceLayerName}")
  QgsProject.instance().addMapLayer(layer, addToLegend=False)
  #messageText = f"gpkgLayerAdd: layer {layerName} from {sourcePackage} added to project"
  #QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  return layer
#
def mergeLayers(settings):
  """RAÄ data delivered by area (kommun, län) is merge into a virtual layer (one for each geometry type) to ease querying etc."""
  projectInstance = QgsProject.instance()
  global symbDir
  global placeKomb
  root = projectInstance.layerTreeRoot()
  dataName = settings['dataName']
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  lamningGroup = root.findGroup(dataName)
  if not lamningGroup.findGroup(placeKomb):
    lamningGroup.insertGroup(0,placeKomb)
  dataGroup = lamningGroup.findGroup(placeKomb)
  selectStr = 'SELECT * FROM '
  preStr = settings['pre']
  postStr = settings['post']
  uniStr = ' UNION ALL '
  sqlQuery = ''
  layerList = []
  # Look through all layers or all ticked layers?
  selectedLayers = selectedGroupLayers()
  for layer in selectedLayers:
    layerSourceName = getLayerSource(layer)
    if 'sverige' in layerSourceName.casefold():
       continue
    if (preStr in layerSourceName or preStr in layer.name()) and postStr in layerSourceName:
      layerList.append(layer.name())
  layerCount= len(layerList)
  for n in range(layerCount):
    s = selectStr + f"'{layerList[n]}'"
    sqlQuery += s
    if n+1 < layerCount:
      sqlQuery += uniStr
  QgsMessageLog.logMessage(f'mergeLayers: {sqlQuery}', 'RAÄ', level = Qgis.Info)
  layerStyle = os.path.join(symbDir, settings['layerStyle'])
  newName1 = preStr.replace('_kommun_','')
  newName1 = newName1.replace('_län_','')
  newName2 = newName1.replace('_',' ')
  newName3 = postStr.replace('_','')
  layerName = f'{dataName} {newName2}, {newName3} join'
  vlayer = QgsVectorLayer(f"?query={sqlQuery}", layerName, "virtual")
  if vlayer.isValid():
    QgsProject.instance().addMapLayer(vlayer, addToLegend=False)
    newTreeLayer = QgsLayerTreeLayer(vlayer) 
    dataGroup.insertChildNode(0, newTreeLayer)
    if os.path.isfile(layerStyle) :
      vlayer.loadNamedStyle(layerStyle)
  return
#
# Insert/Load specific datasets
# RAÄ data
def loadLamningar():
  """Specific function called to update and insert lämningar"""
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Lämningar"
  deDataName = deClutter(dataName)
  try:
    inDir = setInitialPath(deDataName)
  except:
    return
  if inDir == None:
    return
  global symbDir
  if os.path.split(inDir)[1] == deDataName:
    folderPath = inDir
  else:
    folderPath = os.path.join(inDir, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'kommun', "Välj Sverige, län eller kommun", "Välj ett eller flera län/kommuner:")
    if lans == None:
      return
  except:
    messageText = ('open_lans_selector failed')
    QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Critical)
    return
  # Check if there is a ToC group for the object type. If not, make one.
  root = QgsProject.instance().layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  urlBase = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1/" 
  spatialLayers = [['lägesosäkerhet', 'LmningLgsk.qml'], ['polygon', 'LmningPolygon.qml'], ['linestring', 'LmningLinestring.qml'], ['point', 'LmningPoint.qml']]
  nonSpatialLayers = ['egenskap','ingaendelamning']
  # Create functions for use by DownloadManager
  def passedFunction(url, path, settingsList):
    """Settings for loading geopackage layer"""
    for settings in settingsList:
      gpkgLayerInsert(settings)
    return 
  def on_failed(url, path, error):
    messageOut("Download", f"Failed: {path}, error={error}")
    return
  def on_finished():
    messageOut('Nedladdning', f"{url} klart")
    return
  manager = DownloadManager(max_parallel=3)
  manager.jobFinished.connect(on_finished)
  manager.jobFailed.connect(on_failed)
  manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
  def setSettings(gpkgPath, parent, baseName, area):
    settingsList = []
    for layerInfo in spatialLayers:
      settings = {
        'geopackage': gpkgPath,
        'parent': parent,
        'sourceLayer': f'{baseName}_{layerInfo[0]}',
        'layerStyle': os.path.join(symbDir, layerInfo[1]),
        'layerName': f'{layerInfo[0]} lämningar, {area}',
      }
      settingsList.append(settings)
    for table in nonSpatialLayers:
      settings = {
        'geopackage': gpkgPath,
        'parent': parent,
        'sourceLayer': table,
        'layerStyle': '',
        'layerName': f'{table} lämningar, {area}',
      }
      settingsList.append(settings)
    return settingsList
  #
  if downloadType == 'land':
    baseName = 'lämningar_sverige'
    gpkgName = f'{baseName}.gpkg'
    area = 'Sverige'
    parent = dataGroup
    # create path for geopackage
    gpkgPath = os.path.join(folderPath, gpkgName)
    url = f'{urlBase}{gpkgName}'
    settingsList = setSettings(gpkgPath, parent, baseName, area)
    if downloadCheck(gpkgPath):
      manager.add_job(f'{url}', gpkgPath, passedFunction, settingsList)
    else:
      QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
      for settings in settingsList:
        gpkgLayerInsert(settings)
    manager.start()
  elif downloadType == 'län':
    for lanName in lans.keys():
      lanLower = lanName.casefold()
      lanLayerName = lanLower.replace(" ","_")
      if not dataGroup.findGroup(lanName):
        dataGroup.insertGroup(0, lanName)
      parent = dataGroup.findGroup(lanName)
      #
      baseName = f'lämningar_län_{lanLayerName}'
      gpkgName = f'{baseName}.gpkg'
      area = lanName
      # create path for geopackage
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f'{urlBase}lan/{gpkgName}'
      settingsList = setSettings(gpkgPath, parent, baseName, area)
      if downloadCheck(gpkgPath):
        manager.add_job(f'{url}', gpkgPath, passedFunction, settingsList)
      else:
        QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
        for settings in settingsList:
          gpkgLayerInsert(settings)
    manager.start()  
  elif downloadType == 'kommuner':
    for lanName, kommuner in lans.items():
      # Check for a län group in the ToC. If there isn't one make one
      if not dataGroup.findGroup(lanName):
        dataGroup.addGroup(lanName)
      lanGroup = dataGroup.findGroup(lanName)
      # Loop through each län's kommuner
      for kommun in kommuner:
        if not lanGroup.findGroup(kommun):
          lanGroup.addGroup(kommun)
        parent = lanGroup.findGroup(kommun)
        # Reformat kommun name to make geopackage naming
        kommunLower = kommun.casefold()
        kommunLayerName = kommunLower.replace(" ","_")
        baseName = "lämningar_kommun_" + kommunLayerName
        gpkgName = baseName + ".gpkg"
        area = kommun
        # create path for geopackage and check if update needed according to update frequency
        gpkgPath = os.path.join(folderPath, gpkgName)
        url = f'{urlBase}kommun/{gpkgName}'
        settingsList = setSettings(gpkgPath, parent, baseName, area)
        if downloadCheck(gpkgPath):
          manager.add_job(f'{url}', gpkgPath, passedFunction, settingsList)
        else:
          QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
          for settings in settingsList:
            gpkgLayerInsert(settings)
    manager.start()   
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadArkeologi():
  '''Specific function called to update and insert arkeologiska uppdrag'''
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Arkeologiska uppdrag"
  deDataName = deClutter(dataName)
  try:
    inDir = setInitialPath(deDataName)
  except:
    return
  if inDir == None:
    return
  global symbDir
  # Where to save the downloaded files
  if os.path.split(inDir)[1] == deDataName:
    folderPath = inDir
  else:
    folderPath = os.path.join(inDir, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'kommun', "Välj Sverige, län eller kommun", "Välj ett eller flera län/kommuner:")
    if lans == None:
      return
  except:
     messageText = ('open_lans_selector failed')
     QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Critical)
     return
  # Check if there is a ToC group for the object type. If not, make one.
  root = QgsProject.instance().layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  urlBase = "https://pub.raa.se/nedladdning/datauttag/arkeologiska_uppdrag/"
  datas = {}
  datas['und'] = {'baseName': 'undersökningsområden', 'url':urlBase, 'urlAddition':'undersokningsomraden', 'layers':[['polygon', 'ArkUppUnderPolygon.qml'],['point', 'ArkUppUnderPoint.qml']]}
  datas['grv'] = {'baseName': 'grävda_ytor', 'url':urlBase, 'urlAddition':'gravda_ytor', 'layers':[['polygon', 'ArkUppGrav.qml']]}
  #
  def passedFunction(url, path, settingsList):
    """Settings for loading geopackage layer"""
    for settings in settingsList:
      gpkgLayerInsert(settings)
    return 
  def on_failed(url, path, error):
    messageOut("Download", f"Failed: {path}, error={error}")
    return
  def on_finished():
    messageOut('Nedladdning', f"{url} klart")
    return
  manager = DownloadManager(max_parallel=3)
  manager.jobFinished.connect(on_finished)
  manager.jobFailed.connect(on_failed)
  manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
  #
  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"arkeologiska_uppdrag_{data['baseName']}_sverige"
      gpkgName = baseName + ".gpkg"
      area = 'Sverige'
      parent = dataGroup
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      layers = data['layers']
      settingsList = []
      if name == 'und':
        layerNamePart = 'undersökningsområden'
      else:
        layerNamePart = 'Grävda ytor'
      for layerInfo in layers:
        settings = {'parent':parent, 'sourceLayer':f'{baseName}_{layerInfo[0]}', 'layerName':f'{layerInfo[0]} {layerNamePart}, {area}', 'layerStyle':os.path.join(symbDir, layerInfo[1]), 'groupName':dataName, 'geopackage':gpkgPath}
        settingsList.append(settings)
        messageText = messagify(settings)
        QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
      if downloadCheck(gpkgPath):
        messageText = f'------ Downloading {gpkgPath}'
        QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
        manager.add_job(f'{url}.gpkg', gpkgPath, passedFunction, settingsList)
      else:
        QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
        for settings in settingsList:
          gpkgLayerInsert(settings)
    manager.start()
  elif downloadType == 'län':
    for lanName in lans.keys():
      lanLower = lanName.casefold()
      lanLayerName = lanLower.replace(" ","_")
      if not dataGroup.findGroup(lanName):
        dataGroup.insertGroup(0, lanName)
      parent = dataGroup.findGroup(lanName)
      for name, data in datas.items():
        baseName = f"arkeologiska_uppdrag_{data['baseName']}_län_{lanLayerName}"
        gpkgName = baseName + ".gpkg"
        area = lanName
        gpkgPath = os.path.join(folderPath, gpkgName)
        url = f"{data['url']}lan/{data['urlAddition']}/{baseName}"
        layers = data['layers']
        settingsList = []
        if name == 'und':
          layerNamePart = 'undersökningsområden'
        else:
          layerNamePart = 'Grävda ytor'
        for layerInfo in layers:
          settings = {'parent':parent, 'sourceLayer':f'{baseName}_{layerInfo[0]}', 'layerName':f'{layerInfo[0]} {layerNamePart}, {area}', 'layerStyle':os.path.join(symbDir, layerInfo[1]), 'groupName':dataName, 'geopackage':gpkgPath}
          settingsList.append(settings)
          messageText = messagify(settings)
          QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
        if downloadCheck(gpkgPath):
          messageText = f'------ Downloading {gpkgPath}'
          QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
          manager.add_job(f'{url}.gpkg', gpkgPath, passedFunction, settingsList)
        else:
          QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
          for settings in settingsList:
            gpkgLayerInsert(settings)
    manager.start()
  elif downloadType == 'kommuner':
    for lanName, kommuner in lans.items():
      # Check for a län group in the ToC. If there isn't one make one
      if not dataGroup.findGroup(lanName):
        dataGroup.addGroup(lanName)
      lanGroup = dataGroup.findGroup(lanName)
      # Loop through each län's kommuner
      for kommun in kommuner:
        if not lanGroup.findGroup(kommun):
          lanGroup.addGroup(kommun)
        parent = lanGroup.findGroup(kommun)
        # Reformat kommun name to make geopackage naming
        kommunLower = kommun.casefold()
        kommunLayerName = kommunLower.replace(" ","_")
        for name, data in datas.items():
          baseName = f"arkeologiska_uppdrag_{data['baseName']}_kommun_{kommunLayerName}"
          gpkgName = baseName + ".gpkg"
          area = kommun
          gpkgPath = os.path.join(folderPath, gpkgName)
          url = f"{data['url']}kommun/{data['urlAddition']}/{baseName}"
          layers = data['layers']
          settingsList = []
          if name == 'und':
            layerNamePart = 'undersökningsområden'
          else:
            layerNamePart = 'Grävda ytor'
          for layerInfo in layers:
            settings = {'parent':parent, 'sourceLayer':f'{baseName}_{layerInfo[0]}', 'layerName':f'{layerInfo[0]} {layerNamePart}, {area}', 'layerStyle':os.path.join(symbDir, layerInfo[1]), 'groupName':dataName, 'geopackage':gpkgPath}
            settingsList.append(settings)
          if downloadCheck(gpkgPath):
            manager.add_job(f'{url}.gpkg', gpkgPath, passedFunction, settingsList)
          else:
            QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
            for settings in settingsList:
              gpkgLayerInsert(settings)
    manager.start()
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadBebyggelse():
  '''Specific function called to update and insert bebyggelse'''
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Bebyggelse"
  deDataName = deClutter(dataName)
  try:
    inDir = setInitialPath(deDataName)
  except:
    return
  if inDir == None:
    return
  global symbDir
  # Where to save the downloaded files
  if os.path.split(inDir)[1] == deDataName:
    folderPath = inDir
  else:
    folderPath = os.path.join(inDir, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'lan', "Välj Sverige eller län", "Välj ett eller flera län:")
    if lans == None:
      return
  except:
     return
  if downloadType == 'kommuner':
     downloadType = 'län'
     messageOut('Obs!',f'Bebyggelse finns inte kommunvis indelat. Län laddas ned istället', Qgis.Info, 5)
  # Check if there is a ToC group for the object type. If not, make one.
  root = QgsProject.instance().layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  datas = {}
  datas['bms'] = {'baseName': "byggnadsminnen_skyddsomraden_", 'url':"https://pub.raa.se/nedladdning/datauttag/bebyggelse/byggnadsminnen_skyddsomraden/"}
  datas['kib'] = {'baseName': "kulturhistoriskt_inventerad_bebyggelse_", 'url':"https://pub.raa.se/nedladdning/datauttag/bebyggelse/kulturhistoriskt_inventerad_bebyggelse/"}
  #
  def passedFunction(url, path, dummy):
    """Settings for loading geopackage layer"""
    settings = dummy
    return gpkgLayerInsert(settings)
  def on_failed(url, path, error):
    messageOut("Download", f"Failed: {path}, error={error}")
  def on_finished():
    messageOut('Nedladdning', f"{url} klart")
  manager = DownloadManager(max_parallel=3)
  manager.jobFinished.connect(on_finished)
  manager.jobFailed.connect(on_failed)
  manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
  #
  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"{data['baseName']}sverige"
      gpkgName = baseName + ".gpkg"
      area = 'Sverige'
      parent = dataGroup
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      if name == 'bms':
        settings = {'parent':parent, 'sourceLayer':f'{baseName}_polygon', 'layerName':f'Byggnadsminnen - skyddsområden, {area}', 'layerStyle':os.path.join(symbDir, 'Byggnadsminne.qml'), 'groupName':dataName, 'geopackage':gpkgPath}
      elif name == 'kib':
        settings = {'parent':parent, 'sourceLayer':f'{baseName}_polygon', 'layerName':f'Kulturhistoriskt inventerad bebyggelse, {area}', 'layerStyle':os.path.join(symbDir, 'ByggnadKultInv.qml'), 'groupName':dataName, 'geopackage':gpkgPath}
      else:
        messageText = ('Error at callback generation for bebyggelse')
        QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Critical)
        return
      if downloadCheck(gpkgPath):
        manager.add_job(f'{url}.gpkg', gpkgPath, passedFunction, settings)
      else:
        QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
        return gpkgLayerInsert(settings)
    manager.start()
  elif downloadType == 'län':
    for lanName in lans.keys():
      lanLower = lanName.casefold()
      lanLayerName = lanLower.replace(" ","_")
      if not dataGroup.findGroup(lanName):
        dataGroup.insertGroup(0, lanName)
      parent = dataGroup.findGroup(lanName)
      for name, data in datas.items():
        baseName = f"{data['baseName']}{lanLayerName}"
        gpkgName = baseName + ".gpkg"
        gpkgPath = os.path.join(folderPath, gpkgName)
        area = lanName
        url = f"{data['url']}{baseName}"
        if name == 'bms':
          settings = {'parent':parent, 'sourceLayer':f'{baseName}_polygon', 'layerName':f'Byggnadsminnen - skyddsområden, {area}', 'layerStyle':os.path.join(symbDir, 'Byggnadsminne.qml'), 'groupName':dataName, 'geopackage':gpkgPath}
        elif name == 'kib':
          settings = {'parent':parent, 'sourceLayer':f'{baseName}_polygon', 'layerName':f'Kulturhistoriskt inventerad bebyggelse, {area}', 'layerStyle':os.path.join(symbDir, 'ByggnadKultInv.qml'), 'groupName':dataName, 'geopackage':gpkgPath}
        else:
          messageText = ('Error at callback generation for bebyggelse')
          QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Critical)
          return
        if downloadCheck(gpkgPath):
          manager.add_job(f'{url}.gpkg', gpkgPath, passedFunction, settings)
        else:
          QgsMessageLog.logMessage(f'{gpkgPath} finns och är aktuell', 'RAÄ', level = Qgis.Info)
          return gpkgLayerInsert(settings)
      manager.start()
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadVarldsarv():
  '''Specific function called to update and insert Världsarv'''
  dataName = "RAÄ områden"
  deDataName = deClutter(dataName)
  try:
    inDir = setInitialPath(deDataName)
  except:
    return
  if inDir == None:
    return
  global symbDir
  # Where to save the downloaded files
  if os.path.split(inDir)[1] == deDataName:
    folderPath = inDir
  else:
    folderPath = os.path.join(inDir, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  # Define address and layer source names
  url = 'https://pub.raa.se/nedladdning/datauttag/varldsarv/varldsarv_sverige.gpkg'
  baseName = 'varldsarv_sverige'
  gpkgName = f'{baseName}.gpkg'
  sourceUpdateFrequency = 30 # Days. Here unknown but unlikely more frequent than once per month
  area = "Sverige"
  # create path for geopackage
  gpkgPath = os.path.join(folderPath, gpkgName)
  # Does up to date file exist
  down = downloadCheck(gpkgPath, sourceUpdateFrequency)
  # Check if layer already in project
  sourceLayerName = f'{baseName}_polygon'
  layer, parent, index = layerPosition(sourceLayerName)
  if not layer == False:
    parent.removeLayer(layer)
  else:
    # Check if there is a ToC group for the object type. If not, make one.
    root = QgsProject.instance().layerTreeRoot()
    if not root.findGroup(dataName):
      root.insertGroup(0,dataName)
    # Get parent ToC group for layers
    parent = root.findGroup(dataName)
  settings = {'geopackage':gpkgPath, 'parent':parent, 'sourceLayer':sourceLayerName, 'layerStyle':os.path.join(symbDir,'Vrldsarv.qml'), 'layerName':f'Världsarv, Sverige', 'groupName':dataName}
  if down == True:
    def passedFunction(url, path, dummy):
      """Settings for loading geopackage layer. Have to go through this as DownloadManager used by other functions and some of theses require url, path. This pass through only needed because of that. Could rewrite DownloadManager but would need to update all dependent functions."""
      settings = dummy
      return gpkgLayerInsert(settings)
    def on_failed(url, path, error):
      messageOut("Download", f"Failed: {path}, error={error}")
    def on_all_done():
      messageOut("Download", "Filer nedladdade")
    def on_finished():
      messageOut('Nedladdning', f"{url} klart")
    manager = DownloadManager(max_parallel=3)
    manager.jobFinished.connect(on_finished)
    manager.jobFailed.connect(on_failed)
    manager.allFinished.connect(on_all_done)
    manager.add_job(url, gpkgPath, passedFunction, settings)
    manager.start()
  # Add layer to the project if file exists but not in project
  if down == False and layer == False:
    gpkgLayerInsert(settings)
  return
# Reshape RAÄ data layers
def mergeLamningar():
  """Function sends settings, names etc for layers to be merged. MergeLayers function uses these settings plus the layers in marked groups in the legend to combine layers"""
  
  settings = {}
  settings['pre'] = 'lämningar'
  settings['post'] = 'egenskap'
  settings['layerStyle'] = ''
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar'
  settings['post'] = 'ingaendelamning'
  settings['layerStyle'] = ''
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_'
  settings['post'] = '_lägesosäkerhet'
  settings['layerStyle'] = 'LmningLgsk.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'LmningPolygon.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_'
  settings['post'] = '_linestring'
  settings['layerStyle'] = 'LmningLinestring.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_'
  settings['post'] = '_point'
  settings['layerStyle'] = 'LmningPoint.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  return
#
def mergeArkeologi():
  """Merge archeology layers marked in ToC"""
  settings = {}
  settings['pre'] = 'arkeologiska_uppdrag_undersökningsområden_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'ArkUppUnderPolygon.qml'
  settings['dataName'] = 'Arkeologiska uppdrag'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'arkeologiska_uppdrag_undersökningsområden_'
  settings['post'] = '_point'
  settings['layerStyle'] = 'ArkUppUnderPoint.qml'
  settings['dataName'] = 'Arkeologiska uppdrag'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'arkeologiska_uppdrag_grävda_ytor_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'ArkUppGrav.qml'
  settings['dataName'] = 'Arkeologiska uppdrag'
  mergeLayers(settings)
  return
#
def mergeBebyggelse():
  """Function sends settings, names etc for layers to be merged. MergeLayers function uses these settings plus the layers in marked groups in the legend to combine layers"""
  settings = {}
  settings['pre'] = 'byggnadsminnen_skyddsomraden_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'Byggnadsminne.qml'
  settings['dataName'] = 'Bebyggelse'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'kulturhistoriskt_inventerad_bebyggelse_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'ByggnadKultInv.qml'
  settings['dataName'] = 'Bebyggelse'
  mergeLayers(settings)

  return
#
def ingaendeMakeRelations(placeList):
  """Loop through place names and create relation for each, connecting egenskap, ingaende to lämning"""
  for place in placeList:
    QgsMessageLog.logMessage(f'ingaendeMakeRelations: {place}', 'RAÄ', level = Qgis.Info)
    lagL = findLayerByString(place, "lägesosäkerhet")
    ingL = findLayerByString(place, "ingaendelamning")
    egeL = findLayerByString(place, "egenskap")
    # Parent is ingående, child is egenskap
    relIDing = writeRelation(ingL.id(), egeL.id(), "id", "ingaendelamning_id", f'{place} egenskap by ingaendelamning_id')
    # Parent is lägesosäkerhet, child is egenskap
    relIDle = writeRelation(lagL.id(), egeL.id(), "lamning_uuid", "lamning_uuid", f'{place} egenskap by lamning_uuid')
    idList = []
    # if not relIDle == None:
      # idList.append(relIDle)
    # Parent is lägesoäkerhet, child is ingående
    relIDli = writeRelation(lagL.id(), ingL.id(), "lamning_uuid", "lamning_uuid", f'{place} ingående by lamning_uuid')
    if not relIDli == None:
      idList.append(relIDli)
    if len(idList) > 0:
      ingaendeMakeForm(lagL, idList)
      iface.setActiveLayer(lagL)
      QgsMapToolIdentifyFeature(iface.mapCanvas(), lagL)
      iface.actionIdentify().trigger()
  return
#
def ingaendeMakeForm(layer, idList):
  """Write the lägesosäkerhets attribute form to include relations for egenskap and ingaende"""
  config = layer.editFormConfig()
  #root = QgsAttributeEditorContainer('Main', None)
  root = config.invisibleRootContainer()
  root.clear()
  fieldsShown = ['lamning_uuid', 'lamningsnummer', 'inmatningskvalitet', 'definition_av_kvalitet', 'lagesosakerhet_i_meter', 'url']
  for relID in idList:
    relation = QgsProject.instance().relationManager().relation(relID)
    if not relation.isValid():
      raise Exception("Relation not found")
    for fieldName in fieldsShown:
      idx = layer.fields().indexOf(fieldName)
      fieldElement = QgsAttributeEditorField(fieldName, idx, root)
      root.addChildElement(fieldElement)
    relationElement = QgsAttributeEditorRelation(relation.id(), root)
    root.addChildElement(relationElement)
    config.setLayout(Qgis.AttributeFormLayout.TabLayout)
    layer.setEditFormConfig(config)
  return
#
def ingaendePlaceList():
  """Checks highlighted layers/groups for match with 'lämning' and adds geographic location to list."""
  global placeKomb
  placeList = []
  selectedLayers = selectedGroupLayers()
  layer = False # Empty project -> for layer doesnt loop
  for layer in selectedLayers:
    source = layer.source()
    if ".gpkg" in source.lower() and "lämningar" in source.lower():
      parts = source.split("|")
      filePath = os.path.normpath(parts[0])
      file = os.path.basename(filePath)
      layerString = parts[1]
      layerName = layerString.split("=", 1)[1]
      fileName = file.split(".")[0]
      fileNameParts = fileName.split("_")
      placeName = fileNameParts[-1]
    elif "?query=SELECT" in source and "lämningar" in source.lower():
      placeName = placeKomb
    if placeName in placeList:
      continue
    else:
      placeList.append(placeName)
  return placeList

def ingaendeConnect():
  """Trigger for creating relations connecting egenskap with ingående lämning and lämning.
  These are stored in the project as they relate multiple layers, or that's QGIS' excuse. Don't joins do the same?
  """
  placeList = ingaendePlaceList()
  messageText = 'Relation för ingående av:\n'
  for p in placeList:
    messageText += f"{p},\n"
  QgsMessageLog.logMessage(messageText, 'RAÄ', level = Qgis.Info)
  ingaendeMakeRelations(placeList)
  return
