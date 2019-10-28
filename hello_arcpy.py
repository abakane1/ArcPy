# -*- coding: utf-8 -*- #
import arcpy,arcinfo
import os

#
# step 0
# 测试系统的arcpy 是否安装正常
# 获取环境参数

#获取当前工作目录路径
root_path = os.getcwd()
# 矢量存在gdb
vector_data_path = os.path.join(root_path,'forZ.gdb')
# raster 在文件夹内
annualRainRunoff = os.path.join(root_path,'年暴雨径流量.tif')
annualPrecipitation = os.path.join(root_path,'年降水量.tif')
annualEvaporation = os.path.join(root_path,'年蒸发量.tif')
soilAndWaterConservationIndex = os.path.join(root_path,'水土保持综合参数.tif')
# arcpy 配置

arcpy.env.workspace = root_path

# add spatial extension
arcpy.CheckOutExtension("spatial")

def ArcPySpatialReferenceName():
    #print arcpy.Exists("landuse")
    sr = arcpy.Describe(os.path.join(root_path,vector_data_path,"landuse")).spatialReference
    return sr
    #print sr.Name
# step 1
# 根据年降水量等数据，获取坐上右下经纬度坐标和格网大小，利用arcpy生成fish格网和中心点。（面）
# 输入数据：年降水量.tif, 行政边界.shp
# 输出数据：格网.shp, 中心点.shp
# 注意事项：栅格数据需要先统一好栅格大小和空间位置；格网的大小需要根据降水量等等栅格数据的大小和位置来确定。
# ref：https://pro.arcgis.com/en/pro-app/tool-reference/data-management/create-fishnet.htm
# 10/13/2019 -zzl
def fishNet():
    arcpy.env.outputCoordinateSystem = ArcPySpatialReferenceName()
    XMin = arcpy.Raster(annualRainRunoff).extent.XMin
    YMin = arcpy.Raster(annualRainRunoff).extent.YMin
    XMax = arcpy.Raster(annualRainRunoff).extent.XMax
    YMax = arcpy.Raster(annualRainRunoff).extent.YMax
    # Set the origin of the fishnet
    originCoordinate = str(XMin)+" "+str(YMin)
    # Set the orientation
    yAxisCoordinate = str(XMin)+" "+str(YMin+10)
    cornerCoordinat = str(XMax)+" "+str(YMax)
    cellsize = 250 # 正方形，所以只需要一个参数
    outfishnet = 'fishnet.shp'
    arcpy.CreateFishnet_management(out_feature_class=outfishnet, origin_coord=originCoordinate, y_axis_coord=yAxisCoordinate, corner_coord=cornerCoordinat, cell_height= cellsize, cell_width= cellsize,geometry_type='POLYGON')
#fishNet()

# step 2
# 结合年降水量、年蒸发量、暴雨降水量栅格数据，提取到中心点数据里。
# 输入数据：年降水量.tif, 年蒸发量.tif, 中心点.shp
# 输出数据：中心点.shp，属性表里包含了多个栅格数据的属性。
# 注意事项：字段的命名
# ref: https://pro.arcgis.com/en/pro-app/tool-reference/spatial-analyst/extract-multi-values-to-points.htm
# 10/14/2019 zzl
def extractIndexToPointFromRaster():
    # Set local variables
    inPointFeatures = "fishnet_label.shp"
    inRasterList = [[annualRainRunoff, "aRainRun"], [annualEvaporation, "aEvapor"], [annualPrecipitation, "aPrec"], [soilAndWaterConservationIndex,"swConIndex"]]
    # Execute ExtractValuesToPoints
    arcpy.sa.ExtractMultiValuesToPoints(inPointFeatures, inRasterList, "BILINEAR")
# extractIndexToPointFromRaster()

# step 3
# 在格网数据里新增n个字段，用于获取中心点里的属性。
# 输入数据：格网.shp
# 输出数据：格网.shp
# step 4
# 基于位置，把中心点和格网数据进行spatial join.
# 输入数据：中心点.shp, 格网.shp
# 输出数据：格网.shp
# 注意事项：target feature, no fid。
# ref: https://pro.arcgis.com/en/pro-app/tool-reference/analysis/spatial-join.htm
# 10/14/2019 zzl
def extractIndexToPolygonFromPoint():
    inPolygonFeatures = "fishnet.shp"
    inPointFeatures = "fishnet_label.shp"
    # set local variables
    target_features = inPolygonFeatures
    join_features = inPointFeatures
    out_feature_class = "fishnet_indexs.shp"
    arcpy.SpatialJoin_analysis(target_features, join_features, out_feature_class)
# extractIndexToPolygonFromPoint()
# step 5
# 格网与土地利用数据进行union
# 输入数据：格网.shp, landuse.shp
# 输出数据：landuse.shp
def extractBySpatialUnion():
    inFeatures = ["fishnet_indexs.shp", os.path.join(vector_data_path,"landuse")]
    outFeatures = "landuse.shp"
    arcpy.Union_analysis(inFeatures, outFeatures,join_attributes='NO_FID')
# extractBySpatialUnion()
# step 6
# 土地利用数据添加字段，用于存储不同生态系统类型的径流系数(runoff coefficient)、暴雨径流系数(Storm runoff coefficient)。
# 输入数据：landuse.shp, 生态系统径流系数对照表
# 输出数据：landuse.shp
# ref: https://pro.arcgis.com/en/pro-app/tool-reference/data-management/add-fields.htm
# 所用工具：cursor，游标
def addIndexsToPolygon():
    inFeatures = "landuse.shp"
    inFieldList = ['runoffCo','stormRunCo']
    for inFieldName in inFieldList:
        arcpy.AddField_management(inFeatures, inFieldName, "Float")
# addIndexsToPolygon()
# step 7
# 计算水源涵养功能量和价值量
# 输入数据：landuse.shp
# 输出数据：landuse.shp
# 注意事项：需要先增加字段，用于存储功能量和价值量；根据公式，水源涵养量（Water conservation） =（降水量*（1-径流系数）-蒸发量）*面积
# ref1：https://pro.arcgis.com/en/pro-app/tool-reference/data-management/calculate-field.htm
# ref2: https://pro.arcgis.com/en/pro-app/tool-reference/data-management/calculate-field-examples.htm
def calIndexs():
    inFeatures = "landuse.shp"
    inFieldList = ['wCon']
    for inFieldName in inFieldList:
        arcpy.AddField_management(inFeatures, inFieldName, "Float")
        expression = "(!aPrec! * (1 - !runoffCo!) - !aEvapor!) * float(!SHAPE.area!)"
        #codeblock = """
        #def getClass(area,runoffCo,aPrec,aEvapor):
        #    if area > 0:
        #        return (aPrec * (1 - runoffCo) - aEvapor) * area
        #    else:
        #        return 0
        #"""
        arcpy.CalculateField_management(inFeatures, inFieldName, expression, "PYTHON")
# calIndexs()


arcpy.CheckInExtension('spatial')