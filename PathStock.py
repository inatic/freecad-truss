# -*- coding: utf-8 -*-
# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2015 Dan Falck <ddfalck@gmail.com>                      *
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
'''used to create material stock around a machined part- for visualization '''

import FreeCAD
import Part
import PathScripts.PathIconViewProvider as PathIconViewProvider
import PathScripts.PathLog as PathLog
import math

from PySide import QtCore


if False:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

# Qt tanslation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

class StockFromBase():

    def __init__(self, obj, baseObject, neg={'x':1, 'y':1, 'z':1}, pos={'x':1, 'y':1, 'z':1}):
        """
        Make stock from a base shape
	StockFromBase(obj, baseObject, neg={'x':2, 'y':2, 'z':2}, pos={'x':2, 'y':2, 'z':2})
        """

        obj.Proxy = self
        self.obj = obj

        obj.addProperty("App::PropertyString", 'StockType', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Internal representation of stock type"))
        obj.addProperty("App::PropertyLink", "BaseObject", "Base", QtCore.QT_TRANSLATE_NOOP("PathStock", "The shape this stock is derived from"))
        obj.addProperty("App::PropertyLength", "ExtXneg", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in negative X direction"))
        obj.addProperty("App::PropertyLength", "ExtXpos", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in positive X direction"))
        obj.addProperty("App::PropertyLength", "ExtYneg", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in negative Y direction"))
        obj.addProperty("App::PropertyLength", "ExtYpos", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in positive Y direction"))
        obj.addProperty("App::PropertyLength", "ExtZneg", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in negative Z direction"))
        obj.addProperty("App::PropertyLength", "ExtZpos", "Stock", QtCore.QT_TRANSLATE_NOOP("PathStock", "Extra allowance from part bound box in positive Z direction"))

        obj.StockType = 'FromBase'
        obj.setEditorMode('StockType', 2) # hide

        obj.BaseObject = baseObject
        obj.Placement = baseObject.Placement

        obj.ExtXneg = neg['x']
        obj.ExtYneg = neg['y']
        obj.ExtZneg = neg['z']
        obj.ExtXpos = pos['x']
        obj.ExtYpos = pos['y']
        obj.ExtZpos = pos['z']

    def execute(self, obj):
        bb = obj.BaseObject.Shape.BoundBox if obj.BaseObject else None

        PathLog.track(obj.Label, bb)

        # Sometimes, when the Base changes it's temporarily not assigned when
        # Stock.execute is triggered - it'll be set correctly the next time around.
        if bb:
            self.origin = FreeCAD.Vector(bb.XMin-obj.ExtXneg.Value, bb.YMin-obj.ExtYneg.Value, bb.ZMin-obj.ExtZneg.Value)

            self.length = bb.XLength + obj.ExtXneg.Value + obj.ExtXpos.Value
            self.width  = bb.YLength + obj.ExtYneg.Value + obj.ExtYpos.Value
            self.height = bb.ZLength + obj.ExtZneg.Value + obj.ExtZpos.Value

            shape = Part.makeBox(self.length, self.width, self.height, self.origin)
            obj.Shape = shape

        if FreeCAD.GuiUp and obj.ViewObject:
            PathIconViewProvider.ViewProvider(obj.ViewObject, 'Stock')
            obj.ViewObject.Transparency = 90
            obj.ViewObject.DisplayMode = 'Wireframe'

    def onChanged(self, obj, prop):
        if prop in ['ExtXneg', 'ExtXpos', 'ExtYneg', 'ExtYpos', 'ExtZneg', 'ExtZpos'] and not 'Restore' in obj.State:
            self.execute(obj)

    def onDocumentRestored(self, obj):
        if hasattr(obj, 'StockType'):
            obj.setEditorMode('StockType', 2) # hide

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

class StockCreateBox():
    MinExtent = 0.001

    def __init__(self, obj, extent={'x':20, 'y':20, 'z':20}, placement=None):
        """
        Create box as stock 
	StockCreateBox(obj, extent={'x':80, 'y':80, 'z':80}, placement)
        """

        obj.Proxy = self
        self.obj = obj

        obj.addProperty('App::PropertyString', 'StockType', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Internal representation of stock type"))
        obj.StockType = 'CreateBox'
        obj.setEditorMode('StockType', 2) # hide
        obj.addProperty('App::PropertyLength', 'Length', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Length of this stock box"))
        obj.addProperty('App::PropertyLength', 'Width', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Width of this stock box"))
        obj.addProperty('App::PropertyLength', 'Height', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Height of this stock box"))

        obj.Length = extent['x']
        obj.Width  = extent['y']
        obj.Height = extent['z']
    
        if placement:
            obj.Placement = placement

    def execute(self, obj):
        if obj.Length < self.MinExtent:
            obj.Length = self.MinExtent
        if obj.Width < self.MinExtent:
            obj.Width = self.MinExtent
        if obj.Height < self.MinExtent:
            obj.Height = self.MinExtent

        shape = Part.makeBox(obj.Length, obj.Width, obj.Height)
        shape.Placement = obj.Placement
        obj.Shape = shape

        if FreeCAD.GuiUp and obj.ViewObject:
            PathIconViewProvider.ViewProvider(obj.ViewObject, 'Stock')
            obj.ViewObject.Transparency = 90
            obj.ViewObject.DisplayMode = 'Wireframe'

    def onChanged(self, obj, prop):
        if prop in ['Length', 'Width', 'Height'] and not 'Restore' in obj.State:
            self.execute(obj)

    def onDocumentRestored(self, obj):
        if hasattr(obj, 'StockType'):
            obj.setEditorMode('StockType', 2) # hide

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

class StockCreateCylinder():
    MinExtent = 0.001

    def __init__(self, obj, radius=2, height=10, placement=None):
        """
        Create cylinder as stock 
	StockCreateCylinder(obj, 30, 30, placement)
        """

        obj.Proxy = self
        self.obj = obj

        obj.addProperty('App::PropertyString', 'StockType', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Internal representation of stock type"))
        obj.StockType = 'CreateCylinder'
        obj.setEditorMode('StockType', 2) # hide
        obj.addProperty('App::PropertyLength', 'Radius', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Radius of this stock cylinder"))
        obj.addProperty('App::PropertyLength', 'Height', 'Stock', QtCore.QT_TRANSLATE_NOOP("PathStock", "Height of this stock cylinder"))

        obj.Radius = radius
        obj.Height = height

        if placement:
            obj.Placement = placement

    def execute(self, obj):
        if obj.Radius < self.MinExtent:
            obj.Radius = self.MinExtent
        if obj.Height < self.MinExtent:
            obj.Height = self.MinExtent

        shape = Part.makeCylinder(obj.Radius, obj.Height)
        shape.Placement = obj.Placement
        obj.Shape = shape

        if FreeCAD.GuiUp and obj.ViewObject:
            PathIconViewProvider.ViewProvider(obj.ViewObject, 'Stock')
            obj.ViewObject.Transparency = 90
            obj.ViewObject.DisplayMode = 'Wireframe'

    def onChanged(self, obj, prop):
        if prop in ['Radius', 'Height'] and not 'Restore' in obj.State:
            self.execute(obj)

    def onDocumentRestored(self, obj):
        if hasattr(obj, 'StockType'):
            obj.setEditorMode('StockType', 2) # hide

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

def test():

    document = FreeCAD.newDocument()

    # Create stock from base shape

    baseShape = Part.makeBox(60,60,60)
    placement = FreeCAD.Placement(FreeCAD.Vector(-30, -30, -30), FreeCAD.Rotation())
    baseObject = document.addObject('Part::Feature', 'Base')
    baseObject.Shape = baseShape
    baseObject.Placement = placement

    baseStockObject = document.addObject('Part::FeaturePython', 'StockFromBase')
    StockFromBase(baseStockObject, baseObject, {'x':2, 'y':2, 'z':2}, {'x':2, 'y':2, 'z':2})

    # Create stock from box

    placement = FreeCAD.Placement(FreeCAD.Vector(-40, -40, -40), FreeCAD.Rotation())
    boxStockObject = document.addObject('Part::FeaturePython', 'StockCreateBox')
    StockCreateBox(boxStockObject, {'x':80, 'y':80, 'z':80}, placement)

    # Create stock from cylinder

    placement = FreeCAD.Placement(FreeCAD.Vector(0, 0, -50), FreeCAD.Rotation())
    cylinderStockObject = document.addObject('Part::FeaturePython', 'StockCreateCylinder')
    StockCreateCylinder(cylinderStockObject, 50, 100, placement)

    document.recompute()

FreeCAD.Console.PrintLog("Loading PathStock... done\n")
