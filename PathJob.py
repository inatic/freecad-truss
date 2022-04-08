# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2014 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import ArchPanel
import Draft
import FreeCAD
import Part
import Path
import PathScripts.PathIconViewProvider as PathIconViewProvider
import PathScripts.PathLog as PathLog
import PathScripts.PathPreferences as PathPreferences
import PathScripts.PathStock as PathStock
import PathScripts.PathToolController as PathToolController
import PathScripts.PathUtil as PathUtil
import json
from Truss import PathAdaptive
from Truss import PathJobGui
from Truss import PathStock

from PathScripts.PathPostProcessor import PostProcessor
from PySide import QtCore

if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

# Qt tanslation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

def isArchPanelSheet(obj):
    return hasattr(obj, 'Proxy') and isinstance(obj.Proxy, ArchPanel.PanelSheet)

def isResourceClone(obj, propLink, resourceName):
    if hasattr(propLink, 'PathResource') and (resourceName is None or resourceName == propLink.PathResource):
        return True
    return False

def createResourceClone(obj, orig, name, icon):
    if isArchPanelSheet(orig):
        # can't clone panel sheets - they have to be panel sheets
        return orig

    clone = Draft.clone(orig)
    clone.Label = "%s-%s" % (name, orig.Label)
    clone.addProperty('App::PropertyString', 'PathResource')
    clone.PathResource = name
    if clone.ViewObject:
        PathIconViewProvider.Attach(clone.ViewObject, icon)
        clone.ViewObject.Visibility = False
    obj.Document.recompute() # necessary to create the clone shape
    return clone

def createModelResourceClone(obj, orig):
    return createResourceClone(obj, orig, 'Model', 'BaseGeometry')

class ObjectJob:

    def __init__(self, obj):

        self.obj = obj
        obj.Proxy = self
        
        # ADD PROPERTIES

        obj.addProperty("App::PropertyLink", "Stock", "Base", "Solid object to be used as stock.")
        obj.addProperty("App::PropertyLink", "Model", "Base", "The base objects for all operations")
        obj.addProperty("App::PropertyLink", "Operations", "Base", "Compound path of all operations in the order they are processed.")
        obj.addProperty("App::PropertyLinkList", "ToolController", "Base", "Collection of tool controllers available for this job.")

        obj.addProperty("App::PropertyFile", "PostProcessorOutputFile", "Output", "The NC output file for this project")
        obj.addProperty("App::PropertyEnumeration", "PostProcessor", "Output", "Select the Post Processor")
        obj.addProperty("App::PropertyString", "PostProcessorArgs", "Output", "Arguments for the Post Processor, specific to the script")

        obj.addProperty("App::PropertyString", "Description", "Path", "An optional description for this job")
        obj.addProperty("App::PropertyDistance", "GeometryTolerance", "Geometry", "For computing Paths; smaller increases accuracy, but slows down computation")
        obj.GeometryTolerance = PathPreferences.defaultGeometryTolerance()

        obj.Model = obj.Document.addObject("App::DocumentObjectGroup", "Model")
        obj.Operations = obj.Document.addObject("Path::FeatureCompoundPython", "Operations")
        
        # hide some objects and properties
        if obj.Model.ViewObject:
            obj.Model.ViewObject.Visibility = False
        if obj.Operations.ViewObject:
            obj.Operations.ViewObject.Visibility = False
        obj.setEditorMode('Operations', 2)
        obj.setEditorMode('Placement', 2)

        obj.PostProcessor = PathPreferences.allEnabledPostProcessors()
        obj.PostProcessor = 'linuxcnc'
        obj.PostProcessorOutputFile = 'test.ngc'

    def addModel(self, obj, models):
        obj.Model.addObjects([createModelResourceClone(obj, model) for model in models])

    def addStock(self, obj, model, neg, pos):
        obj.Stock = PathStock.CreateFromBase(model, neg=None, pos=None)

    def addOperation(self, op, before = None):
        group = self.obj.Operations.Group
        if op not in group:
            if before:
                try:
                    group.insert(group.index(before), op)
                except Exception as e:
                    PathLog.error(e)
                    group.append(op)
            else:
                group.append(op)
            self.obj.Operations.Group = group
            op.Path.Center = self.obj.Operations.Path.Center

    def addToolController(self, tc):
        group = self.obj.ToolController
        PathLog.debug("addToolController(%s): %s" % (tc.Label, [t.Label for t in group]))
        if tc.Name not in [str(t.Name) for t in group]:
            group.append(tc)
            self.obj.ToolController = group

    def allOperations(self):
        ops = []
        def collectBaseOps(op):
            if hasattr(op, 'TypeId'):
                if op.TypeId == 'Path::FeaturePython':
                    ops.append(op)
                    if hasattr(op, 'Base'):
                        collectBaseOps(op.Base)
                if op.TypeId == 'Path::FeatureCompoundPython':
                    ops.append(op)
                    for sub in op.Group:
                        collectBaseOps(sub)
        for op in self.obj.Operations.Group:
            collectBaseOps(op)
        return ops

    def modelBoundBox(self, obj):
        return PathStock.shapeBoundBox(obj.Model.Group)

    def baseObject(self, obj, base):
        '''Return the base object, not its clone.'''
        if isResourceClone(obj, base, 'Model') or isResourceClone(obj, base, 'Base'):
            return base.Objects[0]
        return base

    def baseObjects(self, obj):
        '''Return the base objects, not their clones.'''
        return [self.baseObject(obj, base) for base in obj.Model.Group]

    def resourceClone(self, obj, base):
        '''resourceClone(obj, base) ... Return the resource clone for base if it exists.'''
        if isResourceClone(obj, base, None):
            return base
        for b in obj.Model.Group:
            if base == b.Objects[0]:
                return b
        return None

    def setCenterOfRotation(self, center):
        if center != self.obj.Path.Center:
            self.obj.Path.Center = center
            self.obj.Operations.Path.Center = center
            for op in self.allOperations():
                op.Path.Center = center

    def execute(self, obj):
        obj.Path = obj.Operations.Path

    def onDocumentRestored(self, obj):
        obj.Proxy = self
        self.obj = obj
        obj.setEditorMode('Operations', 2) # hide
        obj.setEditorMode('Placement', 2)

    def onChanged(self, obj, prop):
        if prop == "PostProcessor" and obj.PostProcessor:
            processor = PostProcessor.load(obj.PostProcessor)
            self.tooltip = processor.tooltip
            self.tooltipArgs = processor.tooltipArgs

    def removeBase(self, obj, base, removeFromModel):
        if isResourceClone(obj, base, None):
            PathUtil.clearExpressionEngine(base)
            if removeFromModel:
                obj.Model.removeObject(base)
            obj.Document.removeObject(base.Name)

    def onDelete(self, obj, arg2=None):
        '''Called by the view provider, there doesn't seem to be a callback on the obj itself.'''
        PathLog.track(obj.Label, arg2)
        doc = obj.Document

        # the first to tear down are the ops, they depend on other resources
        PathLog.debug('taking down ops: %s' % [o.Name for o in self.allOperations()])
        while obj.Operations.Group:
            op = obj.Operations.Group[0]
            if not op.ViewObject or not hasattr(op.ViewObject.Proxy, 'onDelete') or op.ViewObject.Proxy.onDelete(op.ViewObject, ()):
                PathUtil.clearExpressionEngine(op)
                doc.removeObject(op.Name)
        obj.Operations.Group = []
        doc.removeObject(obj.Operations.Name)
        obj.Operations = None

        # stock could depend on Model, so delete it first
        if obj.Stock:
            PathLog.debug('taking down stock')
            PathUtil.clearExpressionEngine(obj.Stock)
            doc.removeObject(obj.Stock.Name)
            obj.Stock = None

        # base doesn't depend on anything inside job
        for base in obj.Model.Group:
            PathLog.debug("taking down base %s" % base.Label)
            self.removeBase(obj, base, False)
        obj.Model.Group = []
        doc.removeObject(obj.Model.Name)
        obj.Model = None

        # Tool controllers don't depend on anything
        PathLog.debug('taking down tool controller')
        for tc in obj.ToolController:
            PathUtil.clearExpressionEngine(tc)
            doc.removeObject(tc.Name)
        obj.ToolController = []
        return True

def test():
    """
    Create a job for testing
    """

    doc = FreeCAD.newDocument()

    type = 'mortise'
    mortiseDepth = 80
    mortiseLength = 70
    mortiseWidth = 30

    # PLACEMENT

    temporaryPosition = FreeCAD.Vector(0,0,0)
    temporaryNormal = FreeCAD.Vector(0,0,1)
    temporaryDirection = FreeCAD.Vector(0,1,0)
    position = FreeCAD.Vector(0,50,50)
    normal = FreeCAD.Vector(0,0,1)
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
    stockShape = stockFace.extrude(-mortiseDepth*temporaryNormal)
    #stockObject = doc.addObject('Part::Feature', 'Stock')
    #stockObject.Shape = stockShape
    #stockObject.Placement = mortisePlacement
    #if stockObject.ViewObject:
    #    stockObject.ViewObject.Visibility = False

    # MORTISE FACE

    length = mortiseLength
    width = mortiseWidth
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
    mortiseShape = mortiseFace.extrude(-mortiseDepth*temporaryNormal)
    mortiseObject = doc.addObject('Part::Feature', 'MortiseFace')
    mortiseObject.Shape = mortiseFace
    mortiseObject.Placement = mortisePlacement
    if mortiseObject.ViewObject:
        mortiseObject.ViewObject.Visibility = False

    # CUTTER

    featureObject = doc.addObject('Part::Feature', 'Feature')
    if type=='mortise':
        cutter = mortiseShape
    else:
        cutter = stockShape.cut(mortiseShape)
    modelShape = stockShape.cut(cutter)
    featureObject.Shape = modelShape
    featureObject.Placement = mortisePlacement

    # DUMMY MORTISE OBJECT

    obj = doc.addObject('Part::FeaturePython', 'Mortise')
    obj.addProperty('Part::PropertyPartShape', 'MortiseFace', 'Faces', 'Mortise').MortiseFace = mortiseFace
    obj.addProperty('Part::PropertyPartShape', 'StockFace', 'Faces', 'Stock').StockFace = stockFace

    # ADAPTIVE OPERATION

    adaptiveResources = {
        'side': 'Outside' if type=='tenon' else 'Inside',
        'finalDepth': -mortiseDepth,
        'position': position,
        'normal': normal,
        'direction': direction
    }
    adaptiveObject = PathAdaptive.create(doc, adaptiveResources)

    ## assign faces of test object to adaptive operation
    adaptiveObject.Stock = (obj, ['StockFace'])
    adaptiveObject.Base = (obj, ['MortiseFace'])

    # JOB

    jobObject = doc.addObject("Path::FeaturePython", "Job")
    ObjectJob(jobObject)
    PathJobGui.ViewProvider(jobObject.ViewObject)
    jobObject.Proxy.addModel(jobObject, [featureObject])
    jobObject.Proxy.addStock(jobObject, jobObject.Model, 1, 1)
    jobObject.Proxy.addOperation(adaptiveObject)

    # TOOL CONTROLLER

    toolController = PathToolController.Create()
    toolController.Label = 'ToolController'
    toolController.ToolNumber = 1
    toolController.VertFeed = 1000
    toolController.HorizFeed = 1000
    toolController.VertRapid = 3000
    toolController.HorizRapid = 3000
    toolController.SpindleDir = 'Forward'
    toolController.SpindleSpeed = 3500
    jobObject.Proxy.addToolController(toolController)
    adaptiveObject.ToolController = toolController

    # TOOL

    tool = Path.Tool()
    tool.Name = '12mm-Endmill'
    tool.ToolType = 'EndMill'
    tool.Material = 'Carbide'
    tool.Diameter = 12
    tool.CuttingEdgeHeight = 100
    tool.LengthOffset = 100
    jobObject.ToolController[0].Tool = tool

    doc.recompute()
