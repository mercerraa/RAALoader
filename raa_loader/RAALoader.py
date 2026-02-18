# -*- coding: utf-8 -*-
# Andrew Mercer
# mercerraa@gmail.com
# Fetch and load RAÄ geopackages into a project
# 12.02.2026
import os
import json
import requests 
import time
from datetime import datetime, timedelta
from qgis.core import ( # pyright: ignore[reportMissingImports]
  Qgis,
  QgsProject,
  QgsVectorLayer,
  QgsLayerTreeLayer,
  QgsLayerTreeGroup,
  QgsDataSourceUri,

)
from qgis.utils import iface # pyright: ignore[reportMissingImports]
from qgis.PyQt.QtWidgets import ( # pyright: ignore[reportMissingImports]
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox
)
from qgis.PyQt.QtCore import ( # pyright: ignore[reportMissingImports]
    Qt
)
###########################
#
thisDir = os.path.dirname(os.path.realpath(os.path.expanduser(__file__)))
#
def messageOut(title, messageText, level=Qgis.Info, duration=3):
    '''Sends message to user via QGIS message bar and to the built in QGIS Python console.
    Levels are Qgis.Info, Qgis.Warning, Qgis.Critical, Qgis.Success
    Good luck trying to find those listed anywhere in the API docs.'''
    iface.messageBar().pushMessage(title, messageText, level, duration)
    print(f'{title}: {messageText}')
#
def setInitialPaths():
  '''Set paths for current project'''
  # Define and set names and paths
  projectInstance = QgsProject.instance()
  projectPath = projectInstance.absolutePath()
  currentDir = os.getcwd()
  if projectPath != currentDir:
    os.chdir(os.path.normpath(projectPath))
    currentDir = os.getcwd()
  # Set path for InData
  inDir = os.path.join(currentDir, 'InData')
  if not os.path.exists(inDir):
    try:
        os.makedirs(inDir)
    except:
       messageOut('ERROR!','Save project to valid location first', Qgis.Critical, 10)
       return
  # Set path for qml files
  symbDir = os.path.join(thisDir, 'Symbology')
  return symbDir, inDir, currentDir, projectInstance
#
def replaceString(filePath, oldStr, newStr):
  '''Search through text file and replace text. Needed for SGU historiska strandlinjer. The qlr file contains absolute paths that need changing to relative'''
  with open(filePath, 'r') as file:
    filedata = file.read()
  filedata = filedata.replace(oldStr, newStr)
  with open(filePath, 'w') as file:
    file.write(filedata)
  return
#
def deSwede(str):
  '''Removes Swedish, non-ascii letters'''
  letters = [ ['Å','A'], ['å','a'], ['Ä','A'], ['ä','a'],['Ö','O'], ['ö','o']]
  for pair in letters:
    str = str.replace(pair[0], pair[1])
  return str
#
def getFileTime(path):
    '''Gets creation and update time stamps of a file.'''
    # elapsed since EPOCH in float
    ti_c = os.path.getctime(path) # Created
    ti_m = os.path.getmtime(path) # Modified
    # Converting the time in seconds to a timestamp
    c_ti = time.ctime(ti_c) # Created
    m_ti = time.ctime(ti_m) # Modified
    return {'createSeconds':ti_c, 'modifySeconds':ti_m, 'createTime':c_ti, 'modifyTime':m_ti}
#
def downloadCheck(gpkgPath, upfrq=30):
  '''Does a source file need updating? This function checks the modification date of a file against the current date. 
  If the difference is greater than the specified update frequency check for a new source data file'''
  todaydt = datetime.now()
  today = todaydt.date()
  down = False
  if os.path.isfile(gpkgPath):
    fileTimeStamp = getFileTime(gpkgPath)
    filedt = datetime.strptime(fileTimeStamp['modifyTime'], "%a %b %d %H:%M:%S %Y")
    if (today - filedt.date()) > timedelta(upfrq):
        down = True
  else:
    down = True
  return down
#
def download_url(url, save_path, chunk_size=128):
    '''Fetches a file from a url.'''
    try:
      r = requests.get(url, stream=True)
      with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
          fd.write(chunk)
      messageOut('Download', f'\n{url} to:\n {save_path}')
      return True
    except requests.exceptions.Timeout:
      download_url(url, save_path, chunk_size)
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
def gpkgLayerInsert(settings):
  """
  """
  filePath = settings['geopackage']
  sourceLayer = settings['sourceLayer']
  layerName = settings['layerName']
  layerStyle = settings['layerStyle']
  parent = settings['parent']
  #groupName = settings['groupName']
  #projectInstance = QgsProject.instance()
  #root = projectInstance.layerTreeRoot()
  newLayer = add_gpkg_layer(filePath, sourceLayer, layerName)
  newTreeLayer = QgsLayerTreeLayer(newLayer)
  parent.insertChildNode(0, newTreeLayer)
  newLayer.loadNamedStyle(layerStyle)
  iface.setActiveLayer(newLayer)
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

  result = layer.saveStyleToDatabase(
    style_name,
    description,
    use_as_default,
    ui_file_content
    )
  if result:
      print(f"{layer.name()} Failed to save style.")
      print(result)
  else:
      print(f"{layer.name()} Style saved successfully.")
  return
    
def getLayerSource(layer):
  """
  Return the actual dataset/layer name from the data source (GeoPackage, Shapefile, PostGIS, etc.)
  not the user-renamed display name.
  Asked ChatGPT for this. There is no built-in for this in QGIS!
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
def layerPosition(sourceLayer):
  '''Function takes a layer name and returns its parent and index in the layer tree
  parent, index = layerPosition(sourceLayer)'''
  projectInstance = QgsProject.instance()
  root = projectInstance.layerTreeRoot()
  parent = False
  index = False
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
    DOWNLOAD_COUNTIES = "län"
    DOWNLOAD_COUNTRY = "land"

    def __init__(self, lans_dict, found_dict):
        super().__init__(iface.mainWindow())
        self.setWindowTitle("Välj Sverige, län eller kommun")
        self.resize(600, 600)
        self.lans_dict = lans_dict
        self.found_dict = found_dict
        self.download_mode = None  

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Välj ett eller flera län/kommuner:"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Område"])
        layout.addWidget(self.tree)

        # --- ROOT: Sverige ---
        self.root_item = QTreeWidgetItem(["Sverige"])
        self.root_item.setFlags(self.root_item.flags() | Qt.ItemIsUserCheckable)
        self.root_item.setCheckState(0, Qt.Unchecked)
        self.tree.addTopLevelItem(self.root_item)
        self.tree.expandAll()
        # --- Populate tree ---
        for parent_name, children in self.lans_dict.items():
            parent_item = QTreeWidgetItem([parent_name])
            parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)
            parent_item.setCheckState(0, Qt.Unchecked)
            self.root_item.addChild(parent_item)

            for child_name in children:
                child_item = QTreeWidgetItem([child_name])
                child_item.setFlags(child_item.flags() | Qt.ItemIsUserCheckable)
                child_item.setCheckState(0, Qt.Unchecked)
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

            parent = parent.parent()

        self.tree.blockSignals(False)

    def handle_accept(self):
      selection, downloadType = self.get_selected_dict()

      sverige_state = self.root_item.checkState(0)

      all_lan_selected = sverige_state == Qt.Checked
      all_kommuner_per_lan = self._all_kommuner_selected(selection)

      # --- CASE 1: Whole country ---
      if all_lan_selected:
          msg = QMessageBox(self)
          msg.setWindowTitle("Hela Sverige valt")
          msg.setText("Hur vill du ladda ner data?")

          btn_country = msg.addButton("En fil för hela Sverige", QMessageBox.AcceptRole)
          btn_lan = msg.addButton("En fil per län", QMessageBox.AcceptRole)
          btn_muni = msg.addButton("En fil per kommun", QMessageBox.AcceptRole)

          msg.exec_()

          if msg.clickedButton() == btn_country:
              self.download_mode = self.DOWNLOAD_COUNTRY
          elif msg.clickedButton() == btn_lan:
              self.download_mode = self.DOWNLOAD_COUNTIES
          elif msg.clickedButton() == btn_muni:
              self.download_mode = self.DOWNLOAD_kommuner
          else:
             return

      # --- CASE 2: Full counties ---
      elif all_kommuner_per_lan:
          msg = QMessageBox(self)
          msg.setWindowTitle("Hela län valt")
          msg.setText("Hur vill du ladda ner data?")

          btn_lan = msg.addButton("En fil per län", QMessageBox.AcceptRole)
          btn_muni = msg.addButton("En fil per kommun", QMessageBox.AcceptRole)

          msg.exec_()

          if msg.clickedButton() == btn_lan:
              self.download_mode = self.DOWNLOAD_COUNTIES
          else:
              self.download_mode = self.DOWNLOAD_kommuner

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
      downloadType = self.download_mode
      for i in range(self.root_item.childCount()):
          parent_item = self.root_item.child(i)
          parent_name = parent_item.text(0)
          parent_state = parent_item.checkState(0)

          # ✔ If whole lan checked → include ALL kommuner
          if parent_state == Qt.Checked:
              selected[parent_name] = list(self.lans_dict[parent_name])
              continue

          selected_children = []
          for j in range(parent_item.childCount()):
              child_item = parent_item.child(j)
              if child_item.checkState(0) == Qt.Checked:
                  selected_children.append(child_item.text(0))

          if selected_children:
              selected[parent_name] = selected_children
      return selected, downloadType

#
def open_lans_selector(datasetName):
    '''Creates a dialog window in QGIS that shows a checkbox list of all län and kommuner in Sweden
     and marks as checked those currently in the group chosen via datasetName'''
    found = getCurrentLayers(datasetName)
    lans = makeAreas(export = False)
    dlg = LansSelectorDialog(lans, found)
    if dlg.exec_():
        selected_dict, downloadType = dlg.get_selected_dict()

        # Display result as message
        if not selected_dict:
            QMessageBox.information(iface.mainWindow(), "Urval", "Inget valt.")
        else:
            msg = "Du har valt:\n\n"
            for k, v in selected_dict.items():
                msg += f"{k}: {', '.join(v) if v else '(hela Län)'}\n"
            QMessageBox.information(iface.mainWindow(), "Urval", msg)

        # You can now use selected_dict programmatically:
        print("Selected structure:", selected_dict)
        print(f'{downloadType}')
        return selected_dict, downloadType
#
def makeAreas(export = False):
  '''Dictionary of all of Swedens län and kommuner. The order follows numerical codes for each län'''
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
  symbPath, inPath, currentDir, projectInstance = setInitialPaths()
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
    #print(f'Looking for {preStr} and {postStr} in {layerSourceName} or {layer.name()}')
    if (preStr in layerSourceName or preStr in layer.name()) and postStr in layerSourceName:
      layerList.append(layer.name())
  #print(f'Layers: {layerList}')
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
  prov = vlayer.dataProvider()
  if not vlayer.isValid():
    print("INVALID virtual layer")
    print(prov.error().summary())
  else:
    print("Layer valid")
    #print("Provider errors:", prov.errors())
    QgsProject.instance().addMapLayer(vlayer, addToLegend=False)
    newTreeLayer = QgsLayerTreeLayer(vlayer) 
    dataGroup.insertChildNode(0, newTreeLayer)
    if os.path.isfile(layerStyle) :
      vlayer.loadNamedStyle(layerStyle)
  return
#
def loadLamningar():
  '''Specific function called to update and insert lämningar'''
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths()
  except:
    return
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Lämningar"
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName)
    if lans == None:
      return
  except:
    return
  
  # Where to save the downloaded files
  deDataName = deSwede(dataName)
  folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,5)

  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)

  urlBase = "https://pub.raa.se/nedladdning/datauttag/lamningar_v1/" 
  layers = [['lägesosäkerhet', 'LmningLgsk.qml'], ['polygon', 'LmningPolygon.qml'], ['linestring', 'LmningLinestring.qml'], ['point', 'LmningPoint.qml']]
  nonSpatial = ['egenskap','ingaendelamning']

  if downloadType == 'land':
    baseName = 'lämningar_sverige'
    gpkgName = f'{baseName}.gpkg'
    # create path for geopackage
    gpkgPath = os.path.join(folderPath, gpkgName)
    url = urlBase + gpkgName
    download_url(url, gpkgPath)
    settings = {}
    settings['geopackage'] = gpkgPath
    settings['parent'] = dataGroup
    for layerInfo in layers:
      settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
      settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
      settings['layerName'] = f'{layerInfo[0]} lämningar, Sverige'
      gpkgLayerInsert(settings)
    for table in nonSpatial:
      settings['sourceLayer'] = table
      settings['layerStyle'] = ''
      settings['layerName'] = f'{table} lämningar, Sverige'
      gpkgLayerInsert(settings)
  #
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
      # create path for geopackage
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f'{urlBase}/lan/{gpkgName}'
      download_url(url, gpkgPath)
      settings = {}
      settings['geopackage'] = gpkgPath
      settings['parent'] = parent
      for layerInfo in layers:
        settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
        settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
        settings['layerName'] = f'{layerInfo[0]} lämningar, {lanName}'
        gpkgLayerInsert(settings)
      for table in nonSpatial:
        settings['sourceLayer'] = table
        settings['layerStyle'] = ''
        settings['layerName'] = f'{table} lämningar, {lanName}'
        gpkgLayerInsert(settings)
  #
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
        # create path for geopackage and check if update needed according to update frequency
        gpkgPath = os.path.join(folderPath, gpkgName)
        url = f'{urlBase}/kommun/{gpkgName}'
        download_url(url, gpkgPath)
        settings = {}
        settings['geopackage'] = gpkgPath
        settings['parent'] = parent
        for layerInfo in layers:
          settings['sourceLayer'] = f'{baseName}_{layerInfo[0]}'
          settings['layerStyle'] = os.path.join(symbPath, layerInfo[1])
          settings['layerName'] = f'{layerInfo[0]} lämningar, {kommun}'
          gpkgLayerInsert(settings)
        for table in nonSpatial:
          settings['sourceLayer'] = table
          settings['layerStyle'] = ''
          settings['layerName'] = f'{table} lämningar, {kommun}'
          gpkgLayerInsert(settings)
  #
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadArkeologi():
  '''Specific function called to update and insert lämningar'''
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths()
  except:
     return
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Arkeologiska uppdrag"
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName)
    if lans == None:
      return
  except:
     return
  # Where to save the downloaded files
  deDataName = deSwede(dataName)
  folderPath = os.path.join(inPath, 'Arkeologiska_uppdrag')
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,5)

  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)

  urlBase = "https://pub.raa.se/nedladdning/datauttag/arkeologiska_uppdrag/"
  datas = {}
  datas['und'] = {'baseName': 'undersökningsområden', 'url':urlBase, 'urlAddition':'undersokningsomraden', 'layers':[ ['polygon', 'ArkUppUnderPolygon.qml','Undersökningsområden'],['point', 'ArkUppUnderPoint.qml','Undersökningsområden']]}
  datas['grv'] = {'baseName': 'grävda_ytor', 'url':urlBase, 'urlAddition':'gravda_ytor', 'layers': [ ['polygon', 'ArkUppGrav.qml','Grävda ytor']]}

  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"arkeologiska_uppdrag_{data['baseName']}_sverige"
      gpkgName = baseName + ".gpkg"
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      download_url(url, gpkgPath)
      # Settings for reading in layers from geopackage
      settings = {}
      settings['geopackage'] = gpkgPath
      settings['parent'] = dataGroup
      for layerData in data['layers']:
        settings['sourceLayer'] = f"{baseName}_{layerData[0]}"
        settings['layerStyle'] = os.path.join(symbPath, layerData[1])
        settings['layerName'] = f"{layerData[2]} Sverige, {layerData[0]}"
        gpkgLayerInsert(settings)
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
        baseName = f"arkeologiska_uppdrag_{data['baseName']}_län_{lanLayerName}"
        gpkgName = baseName + ".gpkg"
        gpkgPath = os.path.join(folderPath, gpkgName)
        url = f"{data['url']}lan/{data['urlAddition']}/{baseName}"
        download_url(url, gpkgPath)
        # Settings for reading in layers from geopackage
        settings = {}
        settings['geopackage'] = gpkgPath
        settings['parent'] = parent
        for layerData in data['layers']:
          settings['sourceLayer'] = f"{baseName}_{layerData[0]}"
          settings['layerStyle'] = os.path.join(symbPath, layerData[1])
          settings['layerName'] = f"{layerData[2]} {lanName}, {layerData[0]}"
          gpkgLayerInsert(settings)
  #
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
          gpkgPath = os.path.join(folderPath, gpkgName)
          url = f"{data['url']}kommun/{data['urlAddition']}/{baseName}"
          download_url(url, gpkgPath)
          # Settings for reading in layers from geopackage
          settings = {}
          settings['geopackage'] = gpkgPath
          settings['parent'] = parent
          for layerData in data['layers']:
            settings['sourceLayer'] = f"{baseName}_{layerData[0]}"
            settings['layerStyle'] = os.path.join(symbPath, layerData[1])
            settings['layerName'] = f"{layerData[2]} {kommun}, {layerData[0]}"
            gpkgLayerInsert(settings)
  #
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadBebyggelse():
  '''Specific function called to update and insert bebyggelse'''
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths()
  except:
     return
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "Bebyggelse"
  # Which kommuner are to be updated or added? Pass the name of the group, e.g. 'Lämningar' or 'Bebyggelse'
  try:
    lans, downloadType = open_lans_selector(dataName)
    if lans == None:
      return
  except:
     return
  if downloadType == 'kommuner':
     downloadType = 'län'
     messageOut('Obs!',f'Bebyggelse finns inte kommunvis indelat. Län laddas ned istället',Qgis.Info,5)
  # Where to save the downloaded files
  deDataName = deSwede(dataName)
  folderPath = os.path.join(inPath, deDataName)
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filerna sparas på {folderPath}',Qgis.Info,5)

  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)

  urlBaseBM = "https://pub.raa.se/nedladdning/datauttag/bebyggelse/byggnadsminnen_skyddsomraden/"
  urlBaseKI = "https://pub.raa.se/nedladdning/datauttag/bebyggelse/kulturhistoriskt_inventerad_bebyggelse/"
  datas = {}
  datas['bms'] = {'baseName': "byggnadsminnen_skyddsomraden_", 'url':urlBaseBM,  'layerStyle': 'Byggnadsminne.qml', 'layerName':'Byggnadsminnen, skyddsområden '}
  datas['kib'] = {'baseName': "kulturhistoriskt_inventerad_bebyggelse_", 'url':urlBaseKI,  'layerStyle': 'ByggnadKultInv.qml', 'layerName':'Kulturhistoriskt inventerad bebyggelse '}

  if downloadType == 'land':
    for name, data in datas.items():
      baseName = f"{data['baseName']}sverige"
      gpkgName = baseName + ".gpkg"
      gpkgPath = os.path.join(folderPath, gpkgName)
      url = f"{data['url']}{baseName}"
      download_url(url, gpkgPath)
      # Settings for reading in layers from geopackage
      settings = {}
      settings['geopackage'] = gpkgPath
      settings['parent'] = dataGroup
      settings['sourceLayer'] = baseName + '_polygon'
      settings['layerStyle'] = os.path.join(symbPath, data['layerStyle'])
      settings['layerName'] = f"{data['layerName']} Sverige"
      gpkgLayerInsert(settings)
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
        url = f"{data['url']}{baseName}"
        download_url(url, gpkgPath)
        # Settings for reading in layers from geopackage
        settings = {}
        settings['geopackage'] = gpkgPath
        settings['parent'] = parent
        settings['sourceLayer'] = baseName + '_polygon'
        settings['layerStyle'] = os.path.join(symbPath, data['layerStyle'])
        settings['layerName'] = f"{data['layerName']} {lanName}"
        gpkgLayerInsert(settings)
  #
  else:
     messageOut('Fel!',f'Om du ser det här har något gått fel. Kontakta utvecklaren',Qgis.Critical,5)
  return
#
def loadVarldsarv():
  '''Specific function called to update and insert Världsarv'''
  try:
    symbPath, inPath, currentDir, projectInstance = setInitialPaths()
  except:
     return
  # Specify which data set Lämningar, Arkeologiska undersökningar, Bebyggelse, Världsarv
  dataName = "RAÄ områden"

  deDataName = deSwede(dataName)
  folderPath = os.path.join(inPath, deDataName.replace(" ","_"))
  if not os.path.isdir(folderPath):
    os.mkdir(folderPath)
  messageOut('Nedladdning',f'Filen sparas på {folderPath}',Qgis.Info,5)

  # Check if there is a ToC group for the object type. If not, make one.
  root = projectInstance.layerTreeRoot()
  if not root.findGroup(dataName):
    root.insertGroup(0,dataName)
  # Get parent ToC group for layers
  dataGroup = root.findGroup(dataName)

  url = 'https://pub.raa.se/nedladdning/datauttag/varldsarv/varldsarv_sverige.gpkg'
  baseName = 'varldsarv_sverige'
  gpkgName = f'{baseName}.gpkg'
  # create path for geopackage
  gpkgPath = os.path.join(folderPath, gpkgName)
  download_url(url, gpkgPath)
  settings = {}
  settings['geopackage'] = gpkgPath
  settings['parent'] = dataGroup
  settings['sourceLayer'] = f'{baseName}_polygon'
  settings['layerStyle'] = os.path.join(symbPath, 'Vrldsarv.qml')
  settings['layerName'] = f'Världsarv, Sverige'
  gpkgLayerInsert(settings)
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
print('Functions:\nloadLamningar()\nloadArkeologi()\nloadBebyggelse()\nloadVarldsarv()')

