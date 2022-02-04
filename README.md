The purpose of this project is to start from a geometric mesh and generate a truss out of wooden beams. Methods for joining the beams would preferably not use any additional fasteners, just features milled out of the wooden stock. The first joinery method being implemented is mortise and tenon, the next candidate being a dovetail joint. The process of going from mesh to truss might look somewhat like the following, though steps will be implemented out of order, tackling the easiest parts first. 

* designing the mesh - we'll start off using Blender as it is great for modelling meshes, though exact dimensioning might not be as straightforward.
* determine beam length - each line in the mesh is a beam, joined with neighbouring beams using a number of wood joinery techniques.
* select joinery technique - a number of techniques like mortise and tenon or dovetail are available for connecting beams.
* find joint parameters - each joints has a placement and number of other parameters depending on the geometric relation between beams.
* model beam - a beam with necessary features is generated
* generate gcode for milling the beam
* machine beam on CNC machine

The last three steps will be a good starting point as it is rather straightforward to model a beam and to create some features to be cut on a CNC. Going from the relationship of lines in the mesh to the parameters of a joint will be the next step. Finally some way of selecting which joint to use in which circumstance will be the last step and admittedly the most dificult. Possibly the user will need to make this choice.

You can think of this document as a companion to the project source code and also as a project diary - it will be updated as the project moves along.

# LIMITATIONS

The machinery used for this project will be rather simple and as inexpensive as possible. One feature that most commercial CNC have, an automatic toolchanger, will not be available because it is expensive. Performing manual tool changes will quickly become impractical when machining many beams, so all features are going to be machined with the same tool. This limits the kinds of shape features that can be machined, but as long as this is kept in mind when designing the joints it will not pose much of a problem. It will also be less than ideal with respect to processing time. The tool itself will be a long endmill, and mainly its diameter will put a lower limit on the radius of corners. Beams will be cut to stock size before being fed in the machine because that's a fast and simple operation. 

Another limitation of the CNC machine is that it has no access to the bottom side of the beam. For now it probably is fine just to turn the beam around when it needs processing from the bottom, and correspondingly have every beam generate two GCode files.

# MODELLING THE BEAM

Designing the beam itself will be one of the more straightforward steps in the project. Each beam has a placement that puts it over the corresponding mesh line in the truss document, and along the positive X-axis when modelled as a single beam in an independent document. All modelling will be done in FreeCAD, which is a CAx package that is especially suited for developing custom functionality due to its open-source nature and the possibility to access most features from a Python script and the built-in console.

## CODE DEVELOPMENT

A built-in Python console (available under **View | Panels | Python Console**) allows for interacting with the application and this is where we will be testing most of our code. The latter is stored in FreeCAD's macro directory, which will differ depending on your operating system. Keep in mind that code needs to be imported each time a change is made, and that repeating the original `import` statement will not do this. The `reload` function of the `importlib` library can be used for this instead.

```
from Truss import beam
import importlib
importlib.reload(beam)
```

## FREECAD OBJECTS

The basic FreeCAD application is mainly concerned with opening documents, saving them, and displaying their content. Other fuctionality is contained in so-called workbenches. The `Part` workbench for example takes care of modelling solid geometry, while the goal of the `Path` workbench is to generate GCode for running on a CNC machine. Each workbench saves its `objects` in the document. These objects are data containers, of which multiple types are available, and attributes can be saved on each object and also stored in the document. Attributes can for example be the length and width of a shape, the radius of a corner, a vector determining the orientation of a shape, etc. Objects are stored in a standard format document (.FCStd), which in fact is nothing more than a ZIP archive that you can extract for having a closer look at its content. It contains, amongst others, an XML file that describes the objects in the document (`Document.xml`). A `GuiDocument.xml` file is also available in the compressed FreeCAD file and contains an XML description of how objects are displayed in the tree view and 3D window of FreeCAD's graphical user interface. It will for example have properties for line color and thickness associated with the objects.

The following command gives an overview of the object types supported by a document, though appropriate modules might need to be loaded for their respective object types to become available:

```
import Part
import Mesh
doc = FreeCAD.newDocument()
doc.supportedTypes()
```

## OBJECT BASED ON A PYTHON SCRIPT

In interesting capability of FreeCAD is that it allows for creating objects according to your own custom Python script. The latter can take care of adding properties to the object, generating shapes, providing functionality for making changes to those shapes, and much more, in fact anything that can be done in Python and with the Python libraries available on the system. 

```
import FreeCAD
doc = FreeCAD.newDocument()
beam = doc.addObject("Part::FeaturePython", "Beam")
beam.addProperty("App::PropertyLength", "Length").Length = 1000.0
```

Should you unzip the FreeCAD document and open the `Document.xml` file it contains, above commands should have created something like the following XML-structured description::

```
<Document SchemaVersion="4">
   <Objects Count="1">
      <Object type="Part::FeaturePython" name="Beam" />
   </Objects>
   <ObjectData Count="1">
      <Object name="Beam">
         <Properties Count="1">            
            <Property name="Length" type="App::PropertyLength">               
                <Float value="1000"/>
            </Property>
         </Properties>
      </Object>
   </ObjectData>
</Document>
```

The Python script itself is not stored in the FreeCAD document, but the module and name of the relevant Python class is added to the object's `Proxy` attribute. When the document is opened, FreeCAD expects to find this class in the Pyton search path and takes care of instantiation, after which it is assigned to the `Proxy` attribute on the object so it can be accessed. We will be storing the script in question in the FreeCAD macro directory. Where this directory is on your system can be found from FreeCAD's drop-down menu at the top of the application by clicking through to FreeCAD | Preferences | General | Macro.

## BASIC BEAM MODEL

Creating a parametric beam shape using a Python script isn't very difficult. Each beam has a couple of basic properties being length, width and height, which are created on the object and will thus be stored in the document. The `Part` workbench comes with a `makeBox` function that can be used to create the final shape. The `FeaturePython` object is passed as an argument when instantiating a beam object. This allows setting properties directly on the object as well as assigning the class instance itself to the `Proxy` attribute. If a property of the object is modified FreeCAD reacts to this by running the `execute` method on the object's `Proxy` attribute.

``` Beam.py
import Part

class beam():
    def __init__(self, obj):
        obj.Proxy = self

        obj.addProperty('App::PropertyLength', 'Length', 'Dimensions', 'Box length').Length = '100 cm'
        obj.addProperty('App::PropertyLength', 'Width', 'Dimensions', 'Box width').Width = '10 cm'
        obj.addProperty('App::PropertyLength', 'Height', 'Dimensions', 'Box height').Height = '10 cm'

    def execute(self, obj):
        """
        Called on document recompute
        """

        beam = Part.makeBox(obj.Length, obj.Width, obj.Height)
        obj.Shape = beam
```

Previous class can be assigned to a `FeaturePython` object, but something is still lacking to display the resulting shape on screen. Rendering on screen requires a separate object, a so-called `ViewProvider`, which attaches to the `ViewObject` attribute of our `FeaturePython` object. The following piece of code is a very basic implementation and does nothing more than assign itself to the ViewObject's Proxy attribute. Many more predefined methods are available to implement different kinds of behaviour. 

``` BeamGui.py
class ViewProvider():

    def __init__(self, obj):
        """
        Set this object to the proxy object of the actual view provider
        """
        obj.Proxy = self

    def attach(self, obj):
        """
        Setup the scene sub-graph of the view provider, this method is mandatory
        """
        return
```

It takes a couple of steps to add a beam to a document: first check if there is an active document and create one if there isn't, add a `Part::FeaturePython` object to this document, assign the Python script to the latter, recompute the document for changes to take effect, and add a ViewProvider to the object in order to show the shape on screen. Before assigning to the `ViewObject` you'll need to make sure the FreeCAD Gui is actually up, otherwise the ViewObject attribute will not be available. Below convenience function takes care of these steps:

``` beam.py
import FreeCAD
from Truss import BeamGui

def test(obj_name):
    doc = FreeCAD.ActiveDocument
    if not doc:
        doc = FreeCAD.newDocument()
    obj = doc.addObject("Part::FeaturePython", obj_name)
    beam(obj)
    doc.recompute()
    if FreeCAd.GuiUp:
        BeamGui.ViewProvider(obj.ViewObject)
    return obj
```

# JOINT FEATURES

Each beam needs to have some machining done in order to fit its neighbouring beams. The location, orientation and other properties of each joint are calculated from the geometry of the original mesh. Each beam has its own coordinate system consisting in an origin and 3 direction vectors, based on which joints are positioned and oriented. The beam can thus be moved around without affecting the relative position of its joints. For now two classic joints types will be implemented, a mortise and tenon joint, and a dovetail joint.

## MORTISE AND TENON JOINT

This type of joint primarily has two features that require milling, a mortise hole and a tenon tongue, and optionally a third feature being a hole to allow for a dowel to keep the assembly together. All three features will be modelled in a single Python class, named `Mortise` for brevity. A `Type` attribute determines if the instance takes the form of a mortise hole, a tenon tongue, or a dowel hole. 

The shapes of the mortise hole, tenon tongue or dowel hole are determined by a number of properties that are stored on the FreeCAD object, in order that they may be saved in the FreeCAD document. Both the hole and the stock have their own length and width, they share a depth parameter. Features are modelled at the origin and in a default (temporary) orientation, after which they are moved and rotated to their proper position. The latter is determined by a position, a normal and a direction vector. The reason for features being modelled at the origin is that the default `PathAdative` operation expects them to be oriented along the positive Z-axis, so its easier to just generate the path there and move it afterwards. Moving is done using the object's `Placement` matrix. The mortise hole is cut out of the stock, and the resulting shape used to cut tenon tongues at the ends of the beam. The tenon tongue shape is used to cut mortise holes in the sides of the beam, and the dowel hole still needs to be implemented. An `OperationExists` property is used to keep track of whether the adaptive milling operation was already created. Because the milling operation links to properties of the mortise object, it is automatically recalculated when any of these properties are modified. 

```
class Mortise():
    """ Create a mortise and tenon joint"""
    def __init__(self, obj):

        obj.Proxy = self

        obj.addProperty('App::PropertyString', 'Description', 'Base', 'Joint description').Description = "Mortise and tenon joint"
        obj.addProperty('App::PropertyEnumeration', 'Type', 'Base', 'Joint type').Type = ["hole","tongue"]
        obj.Type = "hole"

        obj.addProperty('App::PropertyLength', 'HoleLength', 'Dimensions', 'Mortise length').HoleLength = '60 mm'
        obj.addProperty('App::PropertyLength', 'HoleWidth', 'Dimensions', 'Mortise width').HoleWidth = '30 mm'
        obj.addProperty('App::PropertyLength', 'StockLength', 'Dimensions', 'Stock length').StockLength = '102 mm'
        obj.addProperty('App::PropertyLength', 'StockWidth', 'Dimensions', 'Stock width').StockWidth = '102 mm'
        obj.addProperty('App::PropertyLength', 'Depth', 'Dimensions', 'Mortise depth').Depth = '60 mm'

        obj.addProperty('App::PropertyVector', 'TemporaryPosition', 'Orientation', 'Temporary mortise position').TemporaryPosition = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'TemporaryNormal', 'Orientation', 'Temporary mortise normal').TemporaryNormal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'TemporaryDirection', 'Orientation', 'Temporary mortise direction').TemporaryDirection = FreeCAD.Vector(0,1,0)

        obj.addProperty('Part::PropertyPartShape', 'HoleFace', 'Faces', 'Face defining feature')
        obj.addProperty('Part::PropertyPartShape', 'StockFace', 'Faces', 'Face defining stock')

        obj.addProperty('App::PropertyVector', 'Position', 'Orientation', 'Mortise position').Position = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'Normal', 'Orientation', 'Mortise normal').Normal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'Direction', 'Orientation', 'Mortise direction').Direction = FreeCAD.Vector(0,1,0)

        obj.addProperty('App::PropertyBool', 'OperationExists', 'Operations', 'Linked adaptive milling operation exists').OperationExists = False

        self.execute(obj)
```

Separate methods take care of creating the shape of the hole and of the stock, the former having the shape of two semi-circles connected by lines, and the latter that of a simple rectangle. Both methods return a tuple of a face and a shape. The face is used to generate an adaptive toolpath using the `PathAdaptive` script, and the latter is used to cut features out of the solid beam shape.

```
    def getHoleShape(self, obj):
        "Return temporary shape created at the origin and in a default orientation"

        length = obj.HoleLength.Value
        width = obj.HoleWidth.Value

        ## Points in each quadrant
        point0 = FreeCAD.Vector(+width/2, +length/2-width/2, 0)
        point1 = FreeCAD.Vector(-width/2, +length/2-width/2, 0)
        point2 = FreeCAD.Vector(-width/2, -length/2+width/2, 0)
        point3 = FreeCAD.Vector(+width/2, -length/2+width/2, 0)

        line03 = Part.makeLine(point3,point0)
        line21 = Part.makeLine(point1,point2)

        ## Arcs
        ### Midpoints
        point10 = FreeCAD.Vector(0, +length/2, 0)
        point32 = FreeCAD.Vector(0, -length/2, 0)

        arc10 = Part.Edge(Part.Arc(point1,point10,point0))
        arc32 = Part.Edge(Part.Arc(point3,point32,point2))

        ## Face and Shape
        holeWire = Part.Wire([line03,arc32,line21,arc10])
        holeFace = Part.Face(holeWire)
        holeShape = holeFace.extrude(-obj.Depth.Value * obj.TemporaryNormal)

        return holeFace, holeShape

    def getStockShape(self, obj):
        "Return temporary shape created at the origin and in a default orientation"

        length = obj.StockLength.Value
        width = obj.StockWidth.Value

        centerPoint = FreeCAD.Vector(-length/2, -width/2, 0)
        stockFace = Part.makePlane(length, width, centerPoint)
        stockShape = stockFace.extrude(-obj.Depth.Value * obj.TemporaryNormal)

        return stockFace, stockShape
```

The `Mortise` object's `execute` method then takes care of generating the required shapes, cutting the hole out of the stock, and assigning the appropriate shape to the object's `Shape` property depending on whether it is a hole or a tongue. The object's `Placement` attribute takes care of putting the joint component in the proper location and giving it the proper orientation. The last call adds an adaptive milling operation for this feature to the document, it will be discussed in the next section.

```
    def execute(self, obj):
        "Executed on document recomputes"

        holeFace, holeShape = self.getHoleShapes(obj)
        stockFace, stockShape = self.getStockShapes(obj)
        obj.HoleFace = holeFace
        obj.StockFace = stockFace
        cutoutShape = stockShape.cut(holeShape)

        if obj.Type == "hole":
            obj.Shape = holeShape
        else:
            obj.Shape = cutoutShape

        # Placement
        obj.Placement.Base = obj.Position
        rotation1 = FreeCAD.Rotation(obj.TemporaryNormal, obj.Normal)
        rotation2 = FreeCAD.Rotation(obj.TemporaryDirection, obj.Direction)
        obj.Placement.Rotation = rotation1.multiply(rotation2)

        if not obj.OperationExists:
            self.addOperation(obj)
            obj.OperationExists = True
```

A separate method again takes care of adding a couple of mortises to a document and is used for testing. By having a `test` method in the same script one can simply make changes, import the script again with `importlib.reload` and create features using the test method. Reloading a script only applies to the script itself, dependencies are not reloaded, so if the test script would be separate a reload would not apply to the script you're working on. After checking for an active document, below `test` method creates a list of tuples, with each tuple containing properties defining a feature. `Mortise` objects are then created for each feature description and added to the document, after which they are fused together and returned. The fusion makes it each to cut all features from a beam shape.

```
def test():
    """ Add some mortises to a document, for testing """

    document = FreeCAD.ActiveDocument
    if not document:
        document = FreeCAD.newDocument()

    # create some features for testing
    features = [] # orientation = (position, normal, direction, type)

    position = FreeCAD.Vector(0,50,50)
    normal = FreeCAD.Vector(-1,0,0)
    direction = FreeCAD.Vector(0,1,0)
    type = "tongue"
    features.append((position, normal, direction, type))

    position = FreeCAD.Vector(200,0,50)
    normal = FreeCAD.Vector(0,-1,0)
    direction = FreeCAD.Vector(1,0,0)
    type = "hole"
    features.append((position, normal, direction, type))

    position = FreeCAD.Vector(1000,50,50)
    normal = FreeCAD.Vector(1,0,0)
    direction = FreeCAD.Vector(0,1,0)
    type = "tongue"
    features.append((position, normal, direction, type))

    objects = []
    for (position, normal, direction, type) in features:
        objectMortise = document.addObject("Part::FeaturePython", "Mortise")
        Mortise(objectMortise)
        MortiseGui.ViewProviderBox(objectMortise.ViewObject)
        objectMortise.Position = position
        objectMortise.Normal = normal
        objectMortise.Direction = direction
        objectMortise.Type = type
        objects.append(objectMortise)

    # Fusion of features
    objectFusion = document.addObject("Part::MultiFuse","Features")
    objectFusion.Shapes = objects

    document.recompute()
    return objects
```

# GENERATING TOOLPATHS

The `Path` workbench will take care of generating toolpaths that can be run on a CNC machine. A big advantage of the `Path` workbench, for us at least, is that it was mainly written in Python. This makes it quite straightforward to examine how things work and create customizations.

The `PathAdaptive` script is used for creating toolpaths, but it will be somewhat simplified as I don't understand all the ins and outs of the `Path` workbench yet. Instead of getting information like heights and sizes from model and stock shapes, in this context we can directly assign such properties. The `Adaptive2D` class of `libarea`, which generates 2D toolpaths for the `PathAdaptive` script, accepts `Base` and `Stock` shapes as a list of 2D coordinates. Our custom `PathAdaptive` script will generate these lists from faces defined as properties on the feature objects (e.g. `Mortise`). It is my understanding that the `Adaptive2D` class can deal with multiple faces (or regions) for both `Base` and `Stock`, though I haven't tested this and it's not needed here. Once toolpaths are generated at the origin, they are moved and rotated to the appropriate destination based on the `Placement` matrix of the related feature. This functionality still needs to be added, will start from the GCode and be kept in a separate module.

The operation furthermore has a number of properties like `Side` and `OperationType` that are passed to the `Adaptive2d` method of the `libarea` library. Then, `AdaptiveInputState` and `AdaptiveOutputState` properties are there for debugging. The rest of the properties are used for generating GCode, namely those that should normally be on the toolcontroller, as well as heights and clearances, which are typically defined on the `PathOp` object from which all Path operation inherit. For the sake of simplicity they are currently also contained in this custom `PathAdaptive` script.

```
class PathAdaptive():
    """
    Create an adaptive milling operation
    """
    def __init__(self, obj):

        obj.addProperty("App::PropertyLinkSub", "Base", "Base", "Face representing the feature to be machined").Base = None
        obj.addProperty("App::PropertyLinkSub", "Stock", "Base", "Face representing the stock for the operation").Stock = None

        obj.addProperty("App::PropertyEnumeration", "Side", "Adaptive", "Side of selected faces that tool should cut").Side = ['Outside', 'Inside']
        obj.Side = "Inside"
        obj.addProperty("App::PropertyEnumeration", "OperationType", "Adaptive", "Type of adaptive operation").OperationType = ['Clearing', 'Profiling']
        obj.OperationType = "Clearing"
        obj.addProperty("App::PropertyFloat", "Tolerance", "Adaptive",  "Influences accuracy and performance").Tolerance = 0.1
        obj.addProperty("App::PropertyPercent", "StepOver", "Adaptive", "Percent of cutter diameter to step over on each pass").StepOver = 20
        obj.addProperty("App::PropertyDistance", "LiftDistance", "Adaptive", "Lift distance for rapid moves").LiftDistance = 0
        obj.addProperty("App::PropertyDistance", "KeepToolDownRatio", "Adaptive", "Max length compared to distance between points").KeepToolDownRatio= 3.0
        obj.addProperty("App::PropertyDistance", "StockToLeave", "Adaptive", "How much stock to leave (i.e. for finishing operation)").StockToLeave= 0
        obj.addProperty("App::PropertyAngle", "HelixAngle", "Adaptive",  "Helix ramp entry angle (degrees)").HelixAngle = 5
        obj.addProperty("App::PropertyLength", "HelixDiameterLimit", "Adaptive", "Limit helix entry diameter").HelixDiameterLimit = 0.0
        obj.addProperty("App::PropertyBool", "ForceInsideOut", "Adaptive","Force plunging into material inside and clearing towards the edges")
        obj.ForceInsideOut = False

        # Properties for inspecting input to and output from the libarea method
        obj.addProperty("App::PropertyPythonObject", "AdaptiveInputState","Adaptive", "Internal input state").AdaptiveInputState = ""
        obj.addProperty("App::PropertyPythonObject", "AdaptiveOutputState","Adaptive", "Internal output state").AdaptiveOutputState = ""

        # These properties should be placed in a toolcontroller
        obj.addProperty("App::PropertyFloat", "ToolDiameter", "Tool", "Tool diameter").ToolDiameter = 12.0
        obj.addProperty("App::PropertyFloat", "ToolVertSpeed", "Tool", "Vertical speed").Tolerance = 100.0
        obj.addProperty("App::PropertyFloat", "ToolHorizSpeed", "Tool", "Horizontal speed").Tolerance = 100.0

        # These properties might be added to a base operation
        obj.addProperty("App::PropertyDistance", "ClearanceHeight", "Heights", "").ClearanceHeight = 0
        obj.addProperty("App::PropertyDistance", "SafeHeight", "Heights", "").SafeHeight = 0
        obj.addProperty("App::PropertyDistance", "StartDepth", "Heights", "").StartDepth = 0
        obj.addProperty("App::PropertyDistance", "StepDown", "Heights", "").StepDown = 0
        obj.addProperty("App::PropertyDistance", "FinishDepth", "Heights", "").FinishDepth = 0
        obj.addProperty("App::PropertyDistance", "FinalDepth", "Heights", "").FinalDepth = 0

        obj.Proxy = self
```

## CONVERT FACES TO PATHS

From the feature object (e.g. the `Mortise`) we are assigning faces to the `PathAdaptive` class, one for `Base` and another for `Stock`, and these are stored in an `App::PropertyLinkSub` property. The object linked to in this case is the feature (e.g. a `Mortise`), and the subshapes are faces stored on the object, in this case a `HoleFace` and a `StockFace`. Assignment to the `App::PropertyLinkSub` property is done in the form of a tuple containing the object and a list of attributes on this object, the attributes being faces in our case. Unpacking this tuple to get at the faces can be done using the Python `getattr` method. 

```
# assign to App::PropertyLinkSub property
objectAdaptive.Base = (obj, ['HoleFace'])
objectAdaptive.Stock = (obj, ['StockFace'])

# unpack App::PropertyLinkSub property
base = getattr(obj.Base[0], obj.Base[1][0])
stock = getattr(obj.Stock[0], obj.Stock[1][0])
```

The geometry of these `base` and `stock` faces are passed to the `Adaptive2d` class provided by `libarea`. For this they need to be converted from regular faces created by the `Part` workbench to what the `Adaptive2d` class expects, which is a lists of edges, each edges being represented as a list of points, and each point in turn being a list of an x- and a y-coordinate. What is refered to as a path in the `Adaptive2d` class would look something like the following:

```
path = [edge, edge, edge]
edge = [point, point, point]
point = [x,y]
```

You can inspect these `Adaptive2d` input paths by opening the `Pocket.Fcstd` file and inspecting `geometry` and `stockGeometry` attributes of the `AdaptiveInputState` property of the operation.

```
doc = FreeCAD.ActiveDocument
ada = doc.getObject('Adaptive')
base = ada.AdaptiveInputState['geometry']
stock = ada.AdaptiveInputState['stockGeometry']
```

The following method converts a face, or any kind of shape having a list of `Edges` as attribute (e.g. a wire), into a 2d path. It goes through the edges of the shape and uses the `discretize` method to turn each edge into a list of points. These points have [x,y,z] coordinates of which we only need [x,y], so only those are added to the `points2d` list.

```
def shapeToPath2d(shape, deflection=0.0001):
    """
    Accepts a shape as input (face, wire ...) and returns a 2d path. 
    The resulting path consists in a list of edges, with each edge being a list of points, and each point being an [x,y] coordinate.
    """
    path2d = list()
    for edge in shape.Edges:
        points3d = edge.discretize(Deflection=deflection)  # list of points with x,y,z coordinates
        points2d = list()                                  # only need x,y coordinates
        for point in points3d:
            points2d.append([point[0], point[1]])
        path2d.append(points2d)

    return path2d
```

## OPERATION INPUTS

The `execute` method of the object is executed each time one of the properties changes or on a `recompute`, both those set on the object itself and those linking to other objects. It starts by collection a number of parameters for the `area.Adaptive2d` operation, amongst others the base and stock faces. These are converted using above `shapeToPath2d` method. A lower limit is also set on the tolerance passed to the operation, and an operation type is assigned by joining `OperationType` and `Side` strings, using the result to fetch the appropriate operation type attribute as defined in the `area` module.

```
baseFace = getattr(obj.Base[0], obj.Base[1][0])
stockFace = getattr(obj.Stock[0], obj.Stock[1][0])
basePath2d = shapeToPath2d(baseFace)
stockPath2d = shapeToPath2d(stockFace)

if obj.Tolerance<0.001: obj.Tolerance=0.001

operationTypeString = obj.OperationType + obj.Side
operationType = getattr(area.AdaptiveOperationType, operationTypeString)
```

Input parameters are subsequently collected on a dictionary (`inputStateObject`) so they can be compared between executions. If nothing changed in respect to the previous input state (`obj.AdaptiveInputState`) for the `area.Adaptive2d` operation, it does not need to be executed again and the previous results of the operation (`obj.AdaptiveOutputState`) can be used instead. A manual recompute or a change of parameter that does not affect the 2d path (e.g. a height or tool parameter) might have caused the execution.

```
inputStateObject = {
    "tool": float(obj.ToolDiameter),
    "tolerance": float(obj.Tolerance),
    "geometry" : basePath2d,
    "stockGeometry": stockPath2d,
    "stepover" : float(obj.StepOver),
    "effectiveHelixDiameter": float(obj.HelixDiameterLimit.Value),
    "operationType": operationTypeString,
    "side": obj.Side,
    "forceInsideOut" : obj.ForceInsideOut,
    "keepToolDownRatio": obj.KeepToolDownRatio.Value,
    "stockToLeave": float(obj.StockToLeave)
}
```

If something changed in the operation's input state, checked by comparing the previous and the current input state, or if there is no previous output state, the `area.Adaptive2d` operation will be executed.

```
if json.dumps(obj.AdaptiveInputState) != json.dumps(inputStateObject):
     adaptiveResults = None

if obj.AdaptiveOutputState !=None and obj.AdaptiveOutputState != "":
     adaptiveResults = obj.AdaptiveOutputState
else:
     adaptiveResults = None
```

## OPERATION EXECUTION

While the `area.Adaptive2d` is executing it returns paths to a progress function while these are being calculated, this so a user can follow progress on screen. The progress function also provides the possibility to stop execution by setting `True` as its return value. Drawing on screen should only be done when the FreeCAD Gui is up, and the responsiblity for progress being drawn on screen probably passed to the the `PathAdaptiveGui` script. For now the progress function is defined on the `PathAdaptive` object and simply returns `False`.

```
def progressFn(self, tpaths):
    """ Progress callback function, will stop processing of area.Adaptive2d operation when returning True """

    if self.obj.ViewObject:
        # should call PathAdaptiveGui method for drawing path progress on screen
        pass

    return False
```

An `area.Adaptive2d` object is prepared and its attributes are assigned, after which the operation can be executed. The progress callback function (`progressFn`) is fed the toolpaths as they are being generated. Then the results of the operation are added to a list, with each result containing a start point for the helix entering the material, a start point for the adaptive operation, the 2d path of the adaptive operation which consists in a list of [x,y] coordinates, and a return motion type (still need to find out what that is.

```
if adaptiveResults == None:
    a2d = area.Adaptive2d()
    a2d.stepOverFactor = 0.01*obj.StepOver
    a2d.toolDiameter = float(obj.ToolDiameter)
    a2d.helixRampDiameter =  obj.HelixDiameterLimit.Value
    a2d.keepToolDownDistRatio = obj.KeepToolDownRatio.Value
    a2d.stockToLeave = float(obj.StockToLeave)
    a2d.tolerance = float(obj.Tolerance)
    a2d.forceInsideOut = obj.ForceInsideOut
    a2d.opType = operationType
    #EXECUTE
    results = a2d.Execute(stockPath2d, basePath2d, self.progressFn)

    #need to convert results to python object to be JSON serializable
    adaptiveResults = []
    for result in results:
        adaptiveResults.append({
            "HelixCenterPoint": result.HelixCenterPoint,
            "StartPoint": result.StartPoint,
            "AdaptivePaths": result.AdaptivePaths,
            "ReturnMotionType": result.ReturnMotionType })
```

## GCODE GENERATION

# MACHINING THE BEAM

LinuxCNC will be used as controller to process each of the beams in the CNC machine.



# RESOURCES

* [FreeCAD file format](https://wiki.freecadweb.org/File_Format_FCStd)
* [FeaturePython Demo part 1](https://wiki.freecadweb.org/Create_a_FeaturePython_object_part_I)
* [FeaturePython Demo part 2](https://wiki.freecadweb.org/Create_a_FeaturePython_object_part_II)
* [Yorik's book](https://yorikvanhavre.gitbooks.io/a-freecad-manual/content/python_scripting/creating_parametric_objects.html)
* [Powerusers hub](https://wiki.freecadweb.org/index.php?title=Power_users_hub)
