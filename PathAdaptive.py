# /**************************************************************************
# *   Copyright (c) Kresimir Tusek         (kresimir.tusek@gmail.com) 2018  *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This library is free software; you can redistribute it and/or         *
# *   modify it under the terms of the GNU Library General Public           *
# *   License as published by the Free Software Foundation; either          *
# *   version 2 of the License, or (at your option) any later version.      *
# *                                                                         *
# *   This library  is distributed in the hope that it will be useful,      *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this library; see the file COPYING.LIB. If not,    *
# *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
# *   Suite 330, Boston, MA  02111-1307, USA                                *
# *                                                                         *
# ***************************************************************************/

import PathScripts.PathUtils as PathUtils
import Part
import Path
import FreeCAD
from FreeCAD import Console
import time
import json
import math
import area
from Truss import PathAdaptiveGui
from Truss import PathOpGui

def shapeToPath2d(shape, deflection=0.0001):
    """
    Accepts a shape as input (face, wire ...) and returns a 2d path. 
    The resulting path consists in a list of edges, with each edge being a list of points, and each point being an [x,y] coordinate.
    """
    points3d = shape.OuterWire.discretize(Deflection=deflection)
    points2d = list()
    for point in points3d:
        points2d.append([point[0], point[1]])
    path2d = [points2d]

    return path2d

class PathAdaptive():
    """
    Create an adaptive milling operation
    """
    def __init__(self, obj):
        
        obj.addProperty("App::PropertyLinkSub", "Base", "Base", "Face representing the feature to be machined").Base = None
        obj.addProperty("App::PropertyLinkSub", "Stock", "Base", "Face representing the stock for the operation").Stock = None

        obj.addProperty("App::PropertyEnumeration", "Side", "Adaptive", "Side of selected faces that tool should cut").Side = ['Outside', 'Inside']
        obj.Side = "Outside"
        obj.addProperty("App::PropertyEnumeration", "OperationType", "Adaptive", "Type of adaptive operation").OperationType = ['Clearing', 'Profiling']
        obj.OperationType = "Clearing"
        obj.addProperty("App::PropertyFloat", "Tolerance", "Adaptive",  "Influences accuracy and performance").Tolerance = 0.1
        obj.addProperty("App::PropertyPercent", "StepOver", "Adaptive", "Percent of cutter diameter to step over on each pass").StepOver = 20
        obj.addProperty("App::PropertyDistance", "LiftDistance", "Adaptive", "Lift distance for rapid moves").LiftDistance = 1
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
        obj.addProperty("App::PropertyFloat", "ToolVertFeed", "Tool", "Vertical speed").ToolVertFeed = 100.0
        obj.addProperty("App::PropertyFloat", "ToolHorizFeed", "Tool", "Horizontal speed").ToolHorizFeed = 100.0

        # These properties might be added to a base operation
        obj.addProperty("App::PropertyDistance", "ClearanceHeight", "Heights", "").ClearanceHeight = 0
        obj.addProperty("App::PropertyDistance", "SafeHeight", "Heights", "").SafeHeight = 0
        obj.addProperty("App::PropertyDistance", "StartDepth", "Heights", "").StartDepth = 0
        obj.addProperty("App::PropertyDistance", "StepDown", "Heights", "").StepDown = 0
        obj.addProperty("App::PropertyDistance", "FinishStep", "Heights", "").FinishStep = 0
        obj.addProperty("App::PropertyDistance", "FinalDepth", "Heights", "").FinalDepth = 0

        # Properties determining the final placement of the toolpath
        obj.addProperty('App::PropertyVector', 'TemporaryPosition', 'Orientation', 'Temporary mortise position').TemporaryPosition = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'TemporaryNormal', 'Orientation', 'Temporary mortise normal').TemporaryNormal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'TemporaryDirection', 'Orientation', 'Temporary mortise direction').TemporaryDirection = FreeCAD.Vector(0,1,0)

        obj.addProperty('Path::PropertyPath', 'TemporaryPath', 'Path', 'Toolpath for the features as modelled at the origin')

        obj.addProperty('App::PropertyVector', 'Position', 'Orientation', 'Mortise position').Position = FreeCAD.Vector(0,0,0)
        obj.addProperty('App::PropertyVector', 'Normal', 'Orientation', 'Mortise normal').Normal = FreeCAD.Vector(0,0,1)
        obj.addProperty('App::PropertyVector', 'Direction', 'Orientation', 'Mortise direction').Direction = FreeCAD.Vector(0,1,0)

        obj.Proxy = self
        self.obj = obj

    def progressFn(self, tpaths):
        """ Progress callback function, will stop processing of area.Adaptive2d operation when returning True """

        if self.obj.ViewObject:
            # should call PathAdaptiveGui method for drawing path progress on screen
            pass

        return False

    def execute(self, obj):
    
        Console.PrintMessage("*** Adaptive toolpath processing started...\n")
        obj.Path = Path.Path("(calculating...)") #hide old toolpaths during recalculation

        # Fetch and convert faces
        baseFace = getattr(obj.Base[0], obj.Base[1][0])
        stockFace = getattr(obj.Stock[0], obj.Stock[1][0])
        basePath2d = shapeToPath2d(baseFace)
        stockPath2d = shapeToPath2d(stockFace)
        # Set lower limit on tolerance
        if obj.Tolerance<0.001: obj.Tolerance=0.001
        # Set operation type
        operationTypeString = obj.OperationType + obj.Side
        operationType = getattr(area.AdaptiveOperationType, operationTypeString)

        # Put all properties that influence calculation of adaptive base paths here
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
    
        # Check if something changed that requires 2D path recalculation 
        if json.dumps(obj.AdaptiveInputState) != json.dumps(inputStateObject):
             adaptiveResults = None

        # Check if there is a previous output state
        if obj.AdaptiveOutputState !=None and obj.AdaptiveOutputState != "":
             adaptiveResults = obj.AdaptiveOutputState
        else:
             adaptiveResults = None
   
        start=time.time()

        if adaptiveResults == None:
            a2d = area.Adaptive2d()
            a2d.stepOverFactor = 0.01*obj.StepOver
            a2d.toolDiameter = float(obj.ToolDiameter)
            a2d.helixRampDiameter =  obj.HelixDiameterLimit.Value
            a2d.keepToolDownDistRatio = obj.KeepToolDownRatio.Value
            a2d.stockToLeave =float(obj.StockToLeave)
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
    
        obj.AdaptiveInputState = inputStateObject
        obj.AdaptiveOutputState = adaptiveResults

        self.generateGCode(obj, adaptiveResults)

        obj.TemporaryPath = Path.Path(self.commandList)
        obj.Path = obj.TemporaryPath

        self.placeToolpath(obj)

        Console.PrintMessage("*** Done. Elapsed: %f sec\n\n" %(time.time()-start))

    def generateGCode(self, obj, adaptiveResults):
    
        if len(adaptiveResults)==0 or len(adaptiveResults[0]["AdaptivePaths"])==0: return

        self.commandList = []
        self.commandList.append(Path.Command("(Start of adaptive operation)"))

        operationStartPoint = obj.TemporaryPosition + obj.ClearanceHeight.Value*obj.TemporaryNormal.normalize()
        self.commandList.append(Path.Command("G0", {"X": operationStartPoint.x, "Y": operationStartPoint.y, "Z": operationStartPoint.z}))
    
        stepDown = obj.StepDown.Value
        if stepDown<0.1 : stepDown = 0.1
        stepUp =  obj.LiftDistance.Value
        minLiftDistance = obj.ToolDiameter
        if stepUp<minLiftDistance: stepUp = minLiftDistance
        finish_step = obj.FinishStep.Value

        if finish_step>stepDown: finish_step = stepDown
        if float(obj.HelixAngle)<1: obj.HelixAngle=1

        self.depthParameters = PathUtils.depth_params(
          clearance_height=obj.ClearanceHeight.Value,
          safe_height=obj.SafeHeight.Value,
          start_depth=obj.StartDepth.Value,
          step_down=stepDown,
          z_finish_step=finish_step,
          final_depth=obj.FinalDepth.Value,
          user_depths=None)

        passStartDepth = obj.StartDepth.Value
        for passEndDepth in self.depthParameters.data:
            for region in adaptiveResults:
    
                center = region["HelixCenterPoint"]
                start = region["StartPoint"]
                helixRadius = math.sqrt( math.pow(center[0]-start[0], 2) + math.pow(center[1]-start[1], 2) )
    
                #helix ramp
                if helixRadius>0.0001:
                    Console.PrintMessage("Helix radius = %f\n"%helixRadius)
                    self.commandList.append(Path.Command("(Helix to pass depth: %f)"%passEndDepth))

                    startAngle = math.atan2( start[1] - center[1], start[0] - center[0] )
                    helixStart = [center[0] + helixRadius * math.cos(startAngle), center[1] + helixRadius * math.sin(startAngle)]
                    self.commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": obj.ClearanceHeight.Value}))
                    self.commandList.append(Path.Command("G0", {"X": helixStart[0], "Y": helixStart[1], "Z": obj.SafeHeight.Value}))
                    self.commandList.append(Path.Command("G1", {"X": helixStart[0], "Y": helixStart[1], "Z": passStartDepth, "F": obj.ToolVertFeed}))
    
                    # calculate depth per helix revolution
                    circumference = 2*math.pi * helixRadius
                    helixAngleRadians = math.pi * float(obj.HelixAngle)/180.0
                    depthPerRevolution = circumference * math.tan(helixAngleRadians)
                    passDepth = (passStartDepth - passEndDepth)
                    maxRadians =  passDepth / depthPerRevolution *  2 * math.pi

                    currentRadians = 0
                    while currentRadians < maxRadians:
                        x = center[0] + helixRadius * math.cos(currentRadians + startAngle)
                        y = center[1] + helixRadius * math.sin(currentRadians + startAngle)
                        z = passStartDepth - currentRadians / maxRadians * passDepth
                        self.commandList.append(Path.Command("G1", { "X":x, "Y":y, "Z":z, "F": obj.ToolVertFeed}))
                        currentRadians += math.pi/18

                    # one more circle at target depth to make sure center is cleared
                    maxRadians += 2*math.pi
                    while currentRadians < maxRadians:
                        x = center[0] + helixRadius * math.cos(currentRadians + startAngle)
                        y = center[1] + helixRadius * math.sin(currentRadians + startAngle)
                        z = passEndDepth
                        self.commandList.append(Path.Command("G1", { "X":x, "Y":y, "Z":z, "F": obj.ToolHorizFeed}))
                        currentRadians += math.pi/18

                else: # no helix entry
                    self.commandList.append(Path.Command("(Straight to pass depth: %f)"%passEndDepth))
                    self.commandList.append(Path.Command("G0", {"X":start[0], "Y": start[1], "Z": obj.ClearanceHeight.Value}))
                    self.commandList.append(Path.Command("G1", {"X":start[0], "Y": start[1], "Z": passEndDepth,"F": obj.ToolVertFeed}))
    
                lastZ = passEndDepth
                z = obj.ClearanceHeight.Value

                self.commandList.append(Path.Command("(Adaptive toolpath at depth: %f)"%passEndDepth))
                for path in region["AdaptivePaths"]:
                    motionType = path[0]  	#[0] contains motion type
                    for point in path[1]: 	#[1] contains list of points
                        x=point[0]
                        y=point[1]
                        if motionType == area.AdaptiveMotionType.Cutting:
                            z=passEndDepth
                            if z!=lastZ: self.commandList.append(Path.Command("G1", { "Z":z,"F": obj.ToolVertFeed}))
                            self.commandList.append(Path.Command("G1", { "X":x, "Y":y, "F": obj.ToolHorizFeed})) 
                        elif motionType == area.AdaptiveMotionType.LinkClear:
                            z=passEndDepth+stepUp
                            if z!=lastZ: self.commandList.append(Path.Command("G0", { "Z":z}))
                            self.commandList.append(Path.Command("G0", { "X":x, "Y":y}))
                        elif motionType == area.AdaptiveMotionType.LinkNotClear:
                            z=obj.ClearanceHeight.Value
                            if z!=lastZ: self.commandList.append(Path.Command("G0", { "Z":z}))
                            self.commandList.append(Path.Command("G0", { "X":x, "Y":y}))
                            Console.PrintMessage("X= %f, Y= %f" % x,y)
                        lastZ = z
                #return to safe height in this Z pass
                z=obj.ClearanceHeight.Value
                if z!=lastZ: self.commandList.append(Path.Command("G0", { "Z":z}))
                lastZ = z
            passStartDepth=passEndDepth
            #return to safe height in this Z pass
            z=obj.ClearanceHeight.Value
            if z!=lastZ: self.commandList.append(Path.Command("G0", { "Z":z}))
            lastZ = z
        z=obj.ClearanceHeight.Value
        if z!=lastZ: self.commandList.append(Path.Command("G0", { "Z":z}))
        lastZ = z
    
    def placeToolpath(self, obj):
      """
      After generating the toolpath at the origin, translate and rotate each
      GCode command to give the toolpath its intended placement.
      """

      # Complete GCode with coordinates for all axis to make placement more straightforward
      commands = obj.Path.Commands
      for i, command in enumerate(commands):
        if (command.Name == 'G0') or (command.Name == 'G1'):
          if 'X' in command.Parameters:
            previousX = command.Parameters['X']
          else:
            commands[i].X = previousX	# modify in place

          if 'Y' in command.Parameters:
            previousY = command.Parameters['Y']
          else:
            commands[i].Y = previousY	# modify in place

          if 'Z' in command.Parameters:
            previousZ = command.Parameters['Z']
          else:
            commands[i].Z = previousZ  	# modify in place
      obj.Path.Commands = commands

      # Placement used to transform command endpoints
      placement = FreeCAD.Placement()
      placement.Base = obj.Position
      rotation1 = FreeCAD.Rotation(obj.TemporaryNormal, obj.Normal)
      rotation2 = FreeCAD.Rotation(obj.TemporaryDirection, obj.Direction)
      placement.Rotation = rotation1.multiply(rotation2)

      # Create vectors for command endpoints, and move these according to above placement
      commands = obj.Path.Commands
      for i, command in enumerate(commands):
        if (command.Name == 'G0') or (command.Name == 'G1'):
          x = command.Parameters['X']
          y = command.Parameters['Y']
          z = command.Parameters['Z']
          temporaryVector = FreeCAD.Vector(x,y,z)
          vector = placement.multVec(temporaryVector)
          commands[i].X = vector.x
          commands[i].Y = vector.y
          commands[i].Z = vector.z
      obj.Path.Commands = commands

      # Calculate angles of rotational axis (AC or BC)
      toolOrientation = obj.Normal
      rotationAngleA = round(math.degrees(math.atan2(toolOrientation.y, -toolOrientation.z)), 5)
      rotationAngleB = round(math.degrees(math.atan2(toolOrientation.x, -toolOrientation.z)), 5)
      rotationAngleC = round(math.degrees(math.atan2(toolOrientation.y, toolOrientation.x)), 5)
      rotationAxis = 'AC'

      # Orient tool
      if rotationAxis == 'AC':
        command = Path.Command('G0', {'A': rotationAngleA, 'C': rotationAngleC})
      else:
        command = Path.Command('G0', {'B': rotationAngleB, 'C': rotationAngleC})

def test():
    """
    Create an adaptive operation for testing
    """

    doc = FreeCAD.newDocument()

    # PLACEMENT

    temporaryPosition = FreeCAD.Vector(0,0,0)
    temporaryNormal = FreeCAD.Vector(0,0,1)
    temporaryDirection = FreeCAD.Vector(0,1,0)
    position = FreeCAD.Vector(0,50,50)
    normal = FreeCAD.Vector(-1,0,0)
    direction = FreeCAD.Vector(0,1,0)

    mortisePlacement = FreeCAD.Placement()
    mortisePlacement.Base = position
    rotation1 = FreeCAD.Rotation(temporaryNormal, normal)
    rotation2 = FreeCAD.Rotation(temporaryDirection, direction)
    mortisePlacement.Rotation = rotation1.multiply(rotation2)

    # STOCK FACE

    height = 100
    width = 100
    centerPoint = FreeCAD.Vector(-height/2, -width/2, 0)
    stockFace = Part.makePlane(height, width, centerPoint)
    stockObject = doc.addObject('Part::Feature', 'StockFace')
    stockObject.Shape = stockFace
    stockObject.Placement = mortisePlacement
 
    # MORTISE FACE

    length = 70
    width = 30
    ## Points in each quadrant
    point0 = FreeCAD.Vector(+width/2, +length/2-width/2, 0)
    point1 = FreeCAD.Vector(-width/2, +length/2-width/2, 0)
    point2 = FreeCAD.Vector(-width/2, -length/2+width/2, 0)
    point3 = FreeCAD.Vector(+width/2, -length/2+width/2, 0)
    ## Side lines
    line03 = Part.makeLine(point3,point0)
    line21 = Part.makeLine(point1,point2)
    ## Arcs
    point10 = FreeCAD.Vector(0, +length/2, 0)
    point32 = FreeCAD.Vector(0, -length/2, 0)
    arc10 = Part.Edge(Part.Arc(point1,point10,point0))
    arc32 = Part.Edge(Part.Arc(point3,point32,point2))
    ## Face and Shape
    mortiseWire = Part.Wire([line03,arc32,line21,arc10])
    mortiseFace = Part.Face(mortiseWire)
    mortiseObject = doc.addObject('Part::Feature', 'MortiseFace')
    mortiseObject.Shape = mortiseFace
    mortiseObject.Placement = mortisePlacement

    # DUMMY MORTISE OBJECT

    obj = doc.addObject('Part::FeaturePython', 'Mortise')
    obj.addProperty('Part::PropertyPartShape', 'MortiseFace', 'Faces', 'Mortise').MortiseFace = mortiseFace
    obj.addProperty('Part::PropertyPartShape', 'StockFace', 'Faces', 'Stock').StockFace = stockFace

    # ADAPTIVE OPERATION

    adaptiveOperation = doc.addObject("Path::FeaturePython", "Adaptive")
    PathAdaptive(adaptiveOperation)
    viewResources = {
      'name': 'Adaptive',
      'opPageClass': PathAdaptiveGui.TaskPanelOpPage,
      'pixmap': 'Path-Adaptive',
      'menutext': 'Adaptive',
      'tooltip': 'Adaptive Clearing and Profiling'
    }
    PathOpGui.ViewProvider(adaptiveOperation.ViewObject, viewResources)

    ## assign faces of test object to adaptive operation
    adaptiveOperation.Stock = (obj, ['StockFace'])
    adaptiveOperation.Base = (obj, ['MortiseFace'])

    adaptiveOperation.ClearanceHeight = 20
    adaptiveOperation.SafeHeight = 10
    adaptiveOperation.StartDepth = 0
    adaptiveOperation.LiftDistance = 1
    adaptiveOperation.StepDown = 10
    adaptiveOperation.FinishStep = 1
    adaptiveOperation.FinalDepth = -80
    adaptiveOperation.Side = 'Outside' 

    adaptiveOperation.Position = position
    adaptiveOperation.Normal = normal
    adaptiveOperation.Direction = direction

    doc.recompute()

    return adaptiveOperation
