# -*- coding: utf-8 -*-
# Andrew Mercer
# mercerraa@gmail.com
# Fetch and load RAÄ geopackages into a project
# 02.04.2026
import os
import time
from datetime import datetime, timedelta
from qgis.core import ( # pyright: ignore[reportMissingImports]
  Qgis,
  QgsProject,
  QgsVectorLayer,
  QgsLayerTreeLayer,
  QgsLayerTreeGroup,
  QgsDataSourceUri,
  QgsNetworkAccessManager
)
from qgis.utils import iface # pyright: ignore[reportMissingImports]
from qgis.PyQt.QtWidgets import ( # pyright: ignore[reportMissingImports]
  QDialog,
  QVBoxLayout,
  QLabel,
  QPushButton,
  QTreeWidget,
  QTreeWidgetItem,
  QMessageBox,
  QProgressBar,
  QFileDialog
)
from qgis.PyQt.QtCore import ( # pyright: ignore[reportMissingImports]
  Qt,
  QUrl,
  QObject,
  pyqtSignal,
  QIODevice,
  QFile
)
from qgis.PyQt.QtNetwork import( # pyright: ignore[reportMissingImports]
  QNetworkRequest,
  QNetworkReply
)  

###########################
#
thisDir = os.path.dirname(os.path.realpath(os.path.expanduser(__file__)))
#
def messageOut(title, messageText, level=Qgis.Info, duration=3):
  """Sends message to user via QGIS message bar and to the built in QGIS Python console.
  Levels are Qgis.Info, Qgis.Warning, Qgis.Critical, Qgis.Success
  More of a convenience as it has defaults set. Also prints to python console."""
  print(f'Message - {title}: {messageText}')
  iface.messageBar().pushMessage(title, messageText, level, duration)
#
def setInitialPaths(dataFolder='InData'):
  """Set paths for current project"""
  # Define and set names and paths
  projectInstance = QgsProject.instance()
  projectPath = projectInstance.absolutePath()
  currentDir = os.getcwd()
  if projectPath != currentDir and projectPath != '':
    os.chdir(os.path.normpath(projectPath))
    currentDir = os.getcwd()
  iface.messageBar().pushMessage('DATA', 'Var ska filerna sparas', Qgis.Info, 2)
  # Set path for directory window to start in 
  datasetDir = os.path.join(currentDir,dataFolder)
  if os.path.exists(datasetDir):
    defaultDir = datasetDir
  else:
    defaultDir = currentDir
  try:
     inDir = QFileDialog.getExistingDirectory(iface.mainWindow(),"Välj mapp för data",defaultDir,QFileDialog.ShowDirsOnly) ### Qt5 ###
  except:
    inDir = QFileDialog.getExistingDirectory(iface.mainWindow(),"Välj mapp för data",defaultDir,QFileDialog.Option.ShowDirsOnly) ### Qt6 ###
  if not os.path.exists(inDir):
    try:
      inDir = os.path.join(projectPath, 'InData')
      if not os.path.exists(inDir):
        print(f'Trying to make {inDir}')
        os.makedirs(inDir)
      print(f'Valid?:{os.path.exists(inDir)}')
    except:
      messageOut('ERROR!','Ingen giltig mapp angiven', Qgis.Critical, 10)
      return
  symbDir = os.path.join(thisDir, 'Symbology')
  return symbDir, inDir, currentDir, projectInstance
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
def downloadCheck(gpkgPath, upfrq=2):
  """Does a source file need updating? This function checks the modification date of a file against the current date. 
  If the difference is greater than the specified update frequency check for a new source data file"""
  todaydt = datetime.now()
  today = todaydt.date()
  down = False # Do not download the file
  if os.path.isfile(gpkgPath): # Does the file even exist?
    if os.path.getsize(gpkgPath) > 0: # Did a previous download fail? Not full check
      fileTimeStamp = getFileTime(gpkgPath)
      filedt = datetime.strptime(fileTimeStamp['modifyTime'], "%a %b %d %H:%M:%S %Y")
      if (today - filedt.date()) > timedelta(upfrq): # Is the file out of date?
          down = True # Do download the file as existing is too old
  else:
    down = True # Do download the file as none found
  return down
#
def download_url(url, savePath, chunkSize=128):
  """Fetches a file from a url."""
  import requests 
  try:
    r = requests.get(url, stream=True)
    r.raise_for_status()
    totalSize = int(r.headers.get('content-length', 0))
    downloadSize = 0
    progress, pbm = progressDisplay(f'Ladda ner {totalSize}')
    with open(savePath, 'wb') as fd:
      for chunk in r.iter_content(chunk_size=chunkSize):
        if chunk:
          fd.write(chunk)
          downloadSize += len(chunk)
          if totalSize > 0:
            progressValue = int((downloadSize / totalSize) * 100)
            progress.setValue(progressValue)
            iface.mainWindow().repaint()
    messageOut('Download', f'\n{url} to:\n {savePath}')
    iface.messageBar().clearWidgets()
    return True
  except OSError as e:
    messageOut('Exception!',f'OSError: {e}', Qgis.Critical, 5)
    return e
  except IOError as e:
    messageOut('Exception!',f'IOError: {e}', Qgis.Critical, 5)
  except requests.exceptions.Timeout:
    download_url(url, savePath, chunkSize)
    return False
  except requests.exceptions.TooManyRedirects as errto:
    messageOut('Exception!',f'Bad URL: {errto}', Qgis.Critical)
    return False
  except requests.exceptions.HTTPError as errh:
    messageOut('Exception!',f'Http Error: {errh}', Qgis.Critical)
    return False
  except requests.exceptions.ConnectionError as errc:
    messageOut('Exception!', f'Error Connecting:{errc}', Qgis.Critical)
    return False
  except requests.exceptions.RequestException as e:
    messageOut('Exception!',f'Error: {e}', Qgis.Critical)
    return False
#
class gpkgDownloadManager(QObject):
    """Replace use of requests as recommended by QGIS"""
    allFinished = pyqtSignal()
    def __init__(self, parent=None, max_parallel=3):
        super().__init__(parent)
        self.max_parallel = max_parallel
        self.queue = []
        self.active = 0
        self.active_replies = {} #Track replies: {job_id: reply_object}
        self.is_cancelled = False   
    def cancel_all(self):
        """Force stop everything."""
        self.is_cancelled = True
        self.queue = [] # Clear the pending jobs
        # Abort all currently running downloads
        for reply in list(self.active_replies.values()):
            reply.abort()
        self.active_replies.clear()
        self.allFinished.emit()
    def add_job(self, parentGroup, baseName, area, gpkgPath, url, load_callback):
        self.queue.append({
            "parentGroup": parentGroup,
            "baseName": baseName,
            "area": area,
            "path": gpkgPath,
            "url": url,
            "callback": load_callback
        })
    def start(self):
        for _ in range(self.max_parallel):
            self._start_next()
    def _start_next(self):
        if not self.queue and self.active == 0:
            self.allFinished.emit()
            return
        if not self.queue or self.active >= self.max_parallel:
            return
        job = self.queue.pop(0)
        self.active += 1
        job['progress'], job['pbm'] = progressDisplay(job['area'])
        self._download(job)
    def _download(self, job):
        if self.is_cancelled: 
            return
        nam = QgsNetworkAccessManager.instance()
        request = QNetworkRequest(QUrl(job["url"]))
        reply = nam.get(request)
        # Track this specific reply
        job_id = id(job) 
        self.active_replies[job_id] = reply
        #######
        #file_handle = open(job["path"], "wb")
        def on_ready_read():
          file_handle.write(bytes(reply.readAll()))
        # Open file in append mode
        file_handle = QFile(job["path"])
        try:
          if not file_handle.open(QIODevice.WriteOnly):
            return
        except:
          if not file_handle.open(QIODevice.OpenModeFlag.WriteOnly):
            return
        # QNetworkReply can write directly to a QFile object
        reply.readyRead.connect(lambda: file_handle.write(reply.readAll()))
        #######
        def on_progress(received, total):
          if total > 0:
            percent = int((received / total) * 100)
            if job.get("progress"):
              job["progress"].setValue(percent)
              iface.mainWindow().repaint()
        def on_finished():
            if job_id in self.active_replies:
                del self.active_replies[job_id] 
            reply.deleteLater()
            file_handle.close()
            try:
              errorCheck = QNetworkReply.NoError
            except:
              errorCheck = reply.NetworkError.NoError
            if reply.error() == errorCheck:
                job["callback"](job["parentGroup"], job['baseName'] ,job["path"], job["area"])
            else:
               messageOut("Error", f"{job['area']}: {reply.errorString()}", Qgis.Critical)
            self.active -= 1
            self._start_next()
            iface.messageBar().popWidget(job['progress'].parent())
        
        reply.readyRead.connect(on_ready_read)
        reply.downloadProgress.connect(on_progress)
        reply.finished.connect(on_finished)
        
#
def gpkgLayerInsert(settings):
  """
  Add geopackage layer to ToC. Will replace existing layer from same source.
  """
  sourcePackage = settings['geopackage']
  sourceLayer = settings['sourceLayer']
  layerName = settings['layerName']
  layerStyle = settings['layerStyle']
  oldLayer, parent, index = gpkgLayerPosition(sourcePackage, sourceLayer)
  if oldLayer:
    QgsProject.instance().removeMapLayer(oldLayer.id())
  else:
    parent = settings['parent']
    index = 0
  newLayer = add_gpkg_layer(sourcePackage, sourceLayer, layerName)
  newTreeLayer = QgsLayerTreeLayer(newLayer)
  parent.insertChildNode(index, newTreeLayer)
  newLayer.loadNamedStyle(layerStyle)
  iface.setActiveLayer(newLayer)
  layer_node = parent.findLayer(newLayer.id())
  if layer_node:
    layer_node.setExpanded(False)
  if not layerStyle == '': 
    saveStyle(newLayer)
  parent.setExpanded(False)
  return
#
def add_gpkg_layer(sourcePackage, sourceLayerName, layerName):
  '''Adds a layer from a geopackage to the QGIS project but doesn't insert it into the layer tree.
  Not inserting into layer tree is important here for updating an existing layer and putting back at same location in tree.'''
  layer = QgsVectorLayer(f"{sourcePackage}|layername={sourceLayerName}", layerName, "ogr")
  if not layer.isValid():
    raise Exception(f"Could not load layer: {sourceLayerName}")
  QgsProject.instance().addMapLayer(layer, addToLegend=False)
  return layer
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
      print(f"saveStyle()V2: {layer.name()} {result}")
  except:
    result = layer.saveStyleToDatabase(
      style_name,
      description,
      use_as_default,
      ui_file_content
      )
    if not result[1] == '':
      print(f"saveStyle(): {layer.name()} {result}")
  return
    
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
    # GeoPackage URIs look like: 'path/to/file.gpkg|layername=roads'
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
  lans = makeAreas(False)
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
       print("getCurrentLayers failed")
    try:
      lans = makeAreas(export = False)
    except:
       print("makeAreas failed")
    try:
      dlg = LansSelectorDialog(lans, found, smallestRegion, instruction1, instruction2)
      print('dlg created')
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
def makeAreas(export = False):
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
def layers_from_group(group):
  layers = []
  for child in group.children():
    if isinstance(child, QgsLayerTreeLayer):
      layers.append(child.layer())
    elif isinstance(child, QgsLayerTreeGroup):
      layers.extend(layers_from_group(child))
  return layers
#
def selected_group_layers():
  tree_view = iface.layerTreeView()
  selected_nodes = tree_view.selectedNodes()
  all_layers = []
  for node in selected_nodes:
    if isinstance(node, QgsLayerTreeGroup):
      all_layers.extend(layers_from_group(node))
    elif isinstance(node, QgsLayerTreeLayer):
      all_layers.append(node.layer())
  all_layers = list({layer.id(): layer for layer in all_layers}.values())
  return all_layers
#
def mergeLayers(settings):
  projectInstance = QgsProject.instance()
  symbPath = os.path.join(thisDir, 'Symbology')
  root = projectInstance.layerTreeRoot()
  dataName = settings['dataName']
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  dataGroup = root.findGroup(dataName)
  selectStr = 'SELECT * FROM '
  preStr = settings['pre']
  postStr = settings['post']
  uniStr = ' UNION ALL '
  sqlQuery = ''
  layerList = []

  # Look through all layers or all ticked layers?
  selectedLayers = selected_group_layers()
  for layer in selectedLayers: #projectInstance.mapLayers().values():
    #for layer in iface.mapCanvas().layers():
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
  print(sqlQuery)
  layerStyle = os.path.join(symbPath, settings['layerStyle'])
  newName1 = preStr.replace('_kommun_','')
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
def loadLamningar():
  """Specific function called to update and insert lämningar"""
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Lämningar"
  deDataName = deSwede(dataName)
  deDataName = deDataName.replace(" ","_")
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths(deDataName)
  except:
    return
  # Where to save the downloaded files
  if os.path.split(inPath)[1] == deDataName:
    folderPath = inPath
  else:
    folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'kommun', "Välj Sverige, län eller kommun", "Välj ett eller flera län/kommuner:")
    if lans == None:
      return
  except:
    print('open_lans_selector failed')
    return
  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  urlBase = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1/" 
  #
  def make_load_callback():
      """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
      Adapted from odd ChatGPT code"""
      def load_layers(parent, baseName, gpkgPath, area_name):
        """Settings for loading geopackage layer"""
        settings = {
            'geopackage': gpkgPath,
            'parent': parent
        }
        layers = [['lägesosäkerhet', 'LmningLgsk.qml'], ['polygon', 'LmningPolygon.qml'], ['linestring', 'LmningLinestring.qml'], ['point', 'LmningPoint.qml']]
        for layerInfo in layers:
            settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
            settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
            settings['layerName'] = f'{layerInfo[0]} lämningar, {area_name}'
            gpkgLayerInsert(settings)
        nonSpatial = ['egenskap','ingaendelamning']
        for table in nonSpatial:
            settings['sourceLayer'] = table
            settings['layerStyle'] = ''
            settings['layerName'] = f'{table} lämningar, {area_name}'
            gpkgLayerInsert(settings)
      return load_layers
  manager = gpkgDownloadManager(max_parallel=3)
  #
  if downloadType == 'land':
    baseName = 'lämningar_sverige'
    gpkgName = f'{baseName}.gpkg'
    area = 'Sverige'
    parent = dataGroup
    # create path for geopackage
    gpkgPath = os.path.join(folderPath, gpkgName)
    url = f'{urlBase}{gpkgName}'
    #######################################
    callback = make_load_callback()
    if downloadCheck(gpkgPath):
      manager.add_job(parent, baseName, area, gpkgPath, url, callback)
    else:
      # already exists → load immediately
      callback(dataGroup, baseName, gpkgPath, area)
    ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
    #######################################
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
      #######################################
      callback = make_load_callback()
      if downloadCheck(gpkgPath):
        manager.add_job(parent, baseName, area, gpkgPath, url, callback)
      else:
        # already exists → load immediately
        callback(parent, baseName, gpkgPath, area)
      ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
        #######################################
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
        #######################################
        callback = make_load_callback()
        if downloadCheck(gpkgPath):
          manager.add_job(parent, baseName, area, gpkgPath, url, callback)
        else:
          # already exists → load immediately
          callback(parent, baseName, gpkgPath, area)
        ####
      manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
      manager.start()
        #######################################
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadArkeologi():
  '''Specific function called to update and insert arkeologiska uppdrag'''
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Arkeologiska uppdrag"
  deDataName = deSwede(dataName)
  deDataName = deDataName.replace(" ","_")
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths(deDataName)
  except:
     return
  # Where to save the downloaded files
  if os.path.split(inPath)[1] == deDataName:
    folderPath = inPath
  else:
    folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'kommun', "Välj Sverige, län eller kommun", "Välj ett eller flera län/kommuner:")
    if lans == None:
      return
  except:
     print('open_lans_selector failed')
     return
  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  # Note difference in url formulations for national vs local (YAPITFA):
  # https://pub.raa.se/nedladdning/datauttag/arkeologiska_uppdrag/kommun/gravda_ytor/arkeologiska_uppdrag_gr%C3%A4vda_ytor_kommun_ale.gpkg
  # https://pub.raa.se/nedladdning/datauttag/arkeologiska_uppdrag/arkeologiska_uppdrag_gr%C3%A4vda_ytor_sverige.gpkg
  urlBase = "https://pub.raa.se/nedladdning/datauttag/arkeologiska_uppdrag/"
  datas = {}
  datas['und'] = {'baseName': 'undersökningsområden', 'url':urlBase, 'urlAddition':'undersokningsomraden'}
  datas['grv'] = {'baseName': 'grävda_ytor', 'url':urlBase, 'urlAddition':'gravda_ytor'}
  def make_und_callback():
    """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
    Adapted from odd ChatGPT code"""
    def load_layers(parent, baseName, gpkgPath, area_name):
      """Settings for loading geopackage layer"""
      settings = {
        'geopackage': gpkgPath,
        'parent': parent
      }
      layers = [['polygon', 'ArkUppUnderPolygon.qml'],['point', 'ArkUppUnderPoint.qml']]
      for layerInfo in layers:
        settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
        settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
        settings['layerName'] = f'{layerInfo[0]} undersökningsområden, {area_name}'
        gpkgLayerInsert(settings)
    return load_layers
  def make_grv_callback():
    """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
    Adapted from odd ChatGPT code"""
    def load_layers(parent, baseName, gpkgPath, area_name):
      """Settings for loading geopackage layer"""
      settings = {
        'geopackage': gpkgPath,
        'parent': parent
      }
      layers = [['polygon', 'ArkUppGrav.qml']]
      for layerInfo in layers:
        settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
        settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
        settings['layerName'] = f'Grävda ytor, {area_name}'
        gpkgLayerInsert(settings)
    return load_layers
  manager = gpkgDownloadManager(max_parallel=3)
  #
  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"arkeologiska_uppdrag_{data['baseName']}_sverige"
      gpkgName = baseName + ".gpkg"
      area = 'Sverige'
      parent = dataGroup
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      #######################################
      if name == 'und':
        callback = make_und_callback()
      elif name == 'grv':
        callback = make_grv_callback()
      else:
        print('Error at callback generation for archeology')
        return
      if downloadCheck(gpkgPath):
        manager.add_job(parent, baseName, area, gpkgPath, url, callback)
      else:
        # already exists → load immediately
        callback(parent, baseName, gpkgPath, area)
      ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
      #######################################
  elif downloadType == 'län':
    for lanName in lans.keys():
      lanLower = lanName.casefold()
      lanLayerName = lanLower.replace(" ","_")
      if not dataGroup.findGroup(lanName):
        dataGroup.insertGroup(0, lanName)
      parent = dataGroup.findGroup(lanName)
      #
      for name, data in datas.items():
        baseName = f"arkeologiska_uppdrag_{data['baseName']}_län_{lanLayerName}"
        gpkgName = baseName + ".gpkg"
        area = lanName
        gpkgPath = os.path.join(folderPath, gpkgName)
        url = f"{data['url']}lan/{data['urlAddition']}/{baseName}"
        #######################################
        if name == 'und':
          callback = make_und_callback()
        elif name == 'grv':
          callback = make_grv_callback()
        else:
          print('Error at callback generation for archeology')
          return
        if downloadCheck(gpkgPath):
          manager.add_job(parent, baseName, area, gpkgPath, url, callback)
        else:
          # already exists → load immediately
          callback(parent, baseName, gpkgPath, area)
        ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
        #######################################
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
          #######################################
          if name == 'und':
            callback = make_und_callback()
          elif name == 'grv':
            callback = make_grv_callback()
          else:
            print('Error at callback generation for archeology')
            return
          if downloadCheck(gpkgPath):
            manager.add_job(parent, baseName, area, gpkgPath, url, callback)
          else:
            # already exists → load immediately
            callback(parent, baseName, gpkgPath, area)
          ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
          #######################################
  #
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadBebyggelse():
  '''Specific function called to update and insert bebyggelse'''
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Bebyggelse"
  deDataName = deSwede(dataName)
  deDataName = deDataName.replace(" ","_")
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths(deDataName)
  except:
     return
  # Where to save the downloaded files
  if os.path.split(inPath)[1] == deDataName:
    folderPath = inPath
  else:
    folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName, 'lan', "Välj Sverige eller län", "Välj ett eller flera län:")
    if lans == None:
      return
  except:
     return
  if downloadType == 'kommuner':
     downloadType = 'län'
     messageOut('Obs!',f'Bebyggelse finns inte kommunvis indelat. Län laddas ned istället',Qgis.Info,5)
  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)
  # Define address and layer source names
  datas = {}
  datas['bms'] = {'baseName': "byggnadsminnen_skyddsomraden_", 'url':"https://pub.raa.se/nedladdning/datauttag/bebyggelse/byggnadsminnen_skyddsomraden/"}
  datas['kib'] = {'baseName': "kulturhistoriskt_inventerad_bebyggelse_", 'url':"https://pub.raa.se/nedladdning/datauttag/bebyggelse/kulturhistoriskt_inventerad_bebyggelse/"}
  def make_bms_callback():
    """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
    Adapted from odd ChatGPT code"""
    def load_layers(parent, baseName, gpkgPath, area_name):
      """Settings for loading geopackage layer"""
      settings = {
        'geopackage': gpkgPath,
        'parent': parent
      }
      settings['sourceLayer'] = f'{baseName}_polygon'
      settings['layerStyle'] = os.path.join(symbPath, 'Byggnadsminne.qml')
      settings['layerName'] = f'Byggnadsminnen - skyddsområden, {area_name}'
      gpkgLayerInsert(settings)
    return load_layers
  def make_kib_callback():
    """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
    Adapted from odd ChatGPT code"""
    def load_layers(parent, baseName, gpkgPath, area_name):
      """Settings for loading geopackage layer"""
      settings = {
        'geopackage': gpkgPath,
        'parent': parent
      }
      settings['sourceLayer'] = f'{baseName}_polygon'
      settings['layerStyle'] = os.path.join(symbPath, 'ByggnadKultInv.qml')
      settings['layerName'] = f'Kulturhistoriskt inventerad bebyggelse, {area_name}'
      gpkgLayerInsert(settings)
    return load_layers
  manager = gpkgDownloadManager(max_parallel=3)
  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"{data['baseName']}sverige"
      gpkgName = baseName + ".gpkg"
      area = 'Sverige'
      parent = dataGroup
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      #######################################
      if name == 'bms':
        callback = make_bms_callback()
      elif name == 'kib':
        callback = make_kib_callback()
      else:
        print('Error at callback generation for archeology')
        return
      if downloadCheck(gpkgPath):
        manager.add_job(parent, baseName, area, gpkgPath, url, callback)
      else:
        # already exists → load immediately
        callback(parent, baseName, gpkgPath, area)
      ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
      #######################################
  #
  elif downloadType == 'län':
    for lanName in lans.keys():
      lanLower = lanName.casefold()
      lanLayerName = lanLower.replace(" ","_")
      if not dataGroup.findGroup(lanName):
        dataGroup.insertGroup(0, lanName)
      parent = dataGroup.findGroup(lanName)
      #
      for name, data in datas.items():
        baseName = f"{data['baseName']}{lanLayerName}"
        gpkgName = baseName + ".gpkg"
        gpkgPath = os.path.join(folderPath, gpkgName)
        area = lanName
        url = f"{data['url']}{baseName}"
        #######################################
        if name == 'bms':
          callback = make_bms_callback()
        elif name == 'kib':
          callback = make_kib_callback()
        else:
          print('Error at callback generation for archeology')
          return
        if downloadCheck(gpkgPath):
          manager.add_job(parent, baseName, area, gpkgPath, url, callback)
        else:
          # already exists → load immediately
          callback(parent, baseName, gpkgPath, area)
        ####
    manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
    manager.start()
        #######################################
  #
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadVarldsarv():
  '''Specific function called to update and insert Världsarv'''
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "RAÄ områden"
  deDataName = deSwede(dataName)
  deDataName = deDataName.replace(" ","_")
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths(dataName)
  except:
     return
  # Where to save the downloaded files
  if os.path.split(inPath)[1] == deDataName:
    folderPath = inPath
  else:
    folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,3)
  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  parent = root.findGroup(dataName)
  # Define address and layer source names
  url = 'https://pub.raa.se/nedladdning/datauttag/varldsarv/varldsarv_sverige.gpkg'
  baseName = 'varldsarv_sverige'
  gpkgName = f'{baseName}.gpkg'
  area = "Sverige"
  # create path for geopackage
  gpkgPath = os.path.join(folderPath, gpkgName)
  def make_load_callback():
    """Function creating settings dict and calls gpkgLayerInsert function. This is all passed to manager class.
    Adapted from odd ChatGPT code"""
    def load_layers(parent, baseName, gpkgPath, area_name):
      """Settings for loading geopackage layer"""
      settings = {}
      settings['geopackage'] = gpkgPath
      settings['parent'] = parent
      settings['sourceLayer'] = f'{baseName}_polygon'
      settings['layerStyle'] = os.path.join(symbPath, 'Vrldsarv.qml')
      settings['layerName'] = f'Världsarv, Sverige'
      gpkgLayerInsert(settings)
    return load_layers
  manager = gpkgDownloadManager(max_parallel=3)
  #######################################
  callback = make_load_callback()
  if downloadCheck(gpkgPath):
    manager.add_job(parent, baseName, area, gpkgPath, url, callback)
  else:
    # already exists → load immediately
    callback(parent, baseName, gpkgPath, area)
  ####
  manager.allFinished.connect(lambda: messageOut("Klart!", "Projektet uppdaterat"))
  manager.start()
#
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
  settings['pre'] = 'lämningar_kommun_'
  settings['post'] = '_lägesosäkerhet'
  settings['layerStyle'] = 'LmningLgsk.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_kommun_'
  settings['post'] = '_polygon'
  settings['layerStyle'] = 'LmningPolygon.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_kommun_'
  settings['post'] = '_linestring'
  settings['layerStyle'] = 'LmningLinestring.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  settings = {}
  settings['pre'] = 'lämningar_kommun_'
  settings['post'] = '_point'
  settings['layerStyle'] = 'LmningPoint.qml'
  settings['dataName'] = 'Lämningar'
  mergeLayers(settings)

  return
#
def mergeArkeologi():
  
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


