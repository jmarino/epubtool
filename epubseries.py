#!/usr/bin/env python

import argparse
import zipfile
import xml.etree.ElementTree as ET
import re
import copy
import sys


#NOTE: see 2034 kepub
#**TODO** remove old series info before adding new one


settings = {'epub3': False,
            'calibre': True
            }


class Epub:
    # Namespaces
    NS = {'ns0': 'http://www.idpf.org/2007/opf',
          'dc': 'http://purl.org/dc/elements/1.1/'}

    def __init__(self, fileName):
        self._fileName = fileName
        self._contentFileName = None
        self._xml = None               # ElementTree main object
        self._metadataNode = None      # metadata node
        self._version = None
    #__init__

    def findContent(self, zfile):
        """Find location of 'content.opf' file. This is stored in 'META-INF/container.xml'"""
        with zfile.open("META-INF/container.xml") as file:
            xml = ET.fromstring(file.read())
        #with

        self._contentFileName = xml[0][0].attrib['full-path']        # <container> <rootfiles> <rootfile full-path="...">
    #findContent

    def readFile(self):
        try:
            zfile = zipfile.ZipFile(self._fileName)
            self.findContent(zfile)
            #print(f"Found: {self._fileName}")
        except FileNotFoundError:
            print(f"ERROR: File '{self._fileName}' not found. Bailing out.")
            raise FileNotFoundError
        #try

        with zfile.open(self._contentFileName) as file:
            self._xml = ET.fromstring(file.read())
            #with
        zfile.close()

        self._metadataNode = self._xml.find('ns0:metadata', namespaces=Epub.NS)
        if self._metadataNode == None:
            raise Exception("Can't find metadata object")
        #

        if 'version' in self._xml.attrib:
            self._version = self._xml.attrib['version']
        #if
    #readFile

    def saveFile(self):
        elem_tree = ET.ElementTree(self._xml)

        new_zip_filename = self._fileName + '.new'
        # create a temp copy of the archive without filename
        with zipfile.ZipFile(self._fileName, 'r') as zin:
            with zipfile.ZipFile(new_zip_filename, 'w') as zout:
                zout.comment = zin.comment # preserve the comment
                for item in zin.infolist():
                    if item.filename != self._contentFileName:
                        zout.writestr(item, zin.read(item.filename))
                    #
                #for
            #with
        #with

        with zipfile.ZipFile(new_zip_filename, 'a', compression=zipfile.ZIP_DEFLATED) as zout:
            with zout.open(self._contentFileName, 'w') as file:
                elem_tree.write(file)
            #
        #with
        print(f"New epub file: '{new_zip_filename}'")
    #saveFile

    def printMetadata(self):
        tree = ET.ElementTree(self._xml)
        print(f'File: {self._fileName}')
        metadataNode = copy.deepcopy(self._metadataNode)
        ET.indent(metadataNode)
        print('metadata:')
        print(ET.tostring(metadataNode, encoding='unicode'))
    #printMetadata

    def getTitle(self):
        title = None
        subtitle = None
        titleNodes = self._metadataNode.findall('dc:title', namespaces=Epub.NS)
        for node in titleNodes:
            refinesNode = self.findRefines(node, 'title-type')
            if refinesNode != None:
                if refinesNode.text == 'main':
                    title = node.text
                elif refinesNode.text == 'subtitle':
                    subtitle = node.text
                #if
            #if
        #for
        if title == None:
            print("WARNING: unable to find title")
            title = '<missing>'
        #
        return title, subtitle
    #getTitle

    def getAuthors(self):
        authorNodes = self._xml.findall('ns0:metadata/dc:creator', namespaces=Epub.NS)
        if len(authorNodes) == 0:
            print("WARNING: unable to find authors")
            return list()
        #

        authors = list()
        for authorNode in authorNodes:
            authors.append(authorNode.text)
        #for

        return authors
    #getAuthors

    def printInfo(self):
        title, subtitle = self.getTitle()
        authors = self.getAuthors()

        print(f'File: {self._fileName}')
        print(f'  Format: ePub version {self._version}')
        print(f'  Title: {title}')
        if subtitle != None:
            print(f'         {subtitle}')

        if len(authors) == 1:
            print(f'  Author: {authors[0]}')
        else:
            authorsStr = ", ".join(authors)
            print(f'  Authors: {authorsStr}')
        #if

        calName_ele = self._metadataNode.find("meta[@name='calibre:series']")
        calNumber_ele = self._metadataNode.find("meta[@name='calibre:series_index']")
        calName = calName_ele.attrib['content'] if calName_ele!=None else ''
        calNumber = calNumber_ele.attrib['content'] if calNumber_ele!=None else ''

        epub3Name_ele = self._metadataNode.find("meta[@property='belongs-to-collection']")
        epub3Number = ''
        if epub3Name_ele:
            seriesId = epub3Name_ele.attrib['id']
            epub3Number_ele = self._metadataNode.find("meta[@refines='{}']".format(seriesId))
            epub3Number = epub3Number_ele.text if epub3Number_ele!=None else ''
        #fi
        epub3Name = epub3Name_ele.text if epub3Name_ele!=None else ''

        if len(calName) > 0:
            print(f"  Series: {calName} : {calNumber}  (calibre)")
        #if
        if len(epub3Name) > 0:
            print(f"  Series: {epub3Name} : {epub3Number}  (epub3)")
        #if
    #printInfo

    def findRefinesById(self, idName, propertyName):
        """Find a meta refines node that refines id 'idName' and has property 'propertyName'"""
        if idName == None:
            return None
        for node in self._metadataNode.findall('./*[@refines="#{idName}"]'):
            if 'property' in node.attrib and node.attrib['property'] == propertyName:
                return node
            #
        #for
        return None
    #findRefinesById

    def findRefines(self, node, propertyName):
        """Find a meta refines node that refines id 'idName' and has property 'propertyName'"""
        if node == None or (not 'id' in node.attrib):
            return None
        idName = node.attrib['id']
        for metaNode in self._metadataNode.findall(f'./*[@refines="#{idName}"]'):
            if 'property' in metaNode.attrib and metaNode.attrib['property'] == propertyName:
                return metaNode
            #
        #for
        return None
    #findRefines


    def deleteRefinesById(self, idName):
        """Delete refines associated with 'idName'"""
        if idName == None:
            return

        for refineNode in self._metadataNode.findall(f'.//*[@refines="#{idName}"]'):
            self._metadataNode.remove(refineNode)
        #if
    #deleteRefinesById

    def deleteRefines(self, node):
        """Delete refines associated with 'node'"""
        if node == None:
            return

        if 'id' in node.attrib:
            idName = node.attrib['id']
            for refineNode in self._metadataNode.findall(f'.//*[@refines="#{idName}"]'):
                self._metadataNode.remove(refineNode)
            #for
        #if
    #deleteRefines

    def deleteNode(self, node):
        """Delete node with all its refines"""
        if node == None:
            return
        #if
        self.deleteRefines(node)
        self._metadataNode.remove(node)
    #deleteNode

    def setTitle(self, newTitle, newSubtitle):
        titleNodes = self._xml.findall('ns0:metadata/dc:title', namespaces=Epub.NS)
        if len(titleNodes) == 0:
            raise Exception("Can't find title in metadata")
        #

        maintitleNode = None
        subtitleNode = None
        for node in titleNodes:
            refinesNode = self.findRefines(node, 'title-type')
            if refinesNode != None:
                if refinesNode.text == "main":
                    maintitleNode = node
                elif refinesNode.text == 'subtitle':
                    subtitleNode = node
                #if
            #if
        #for
        if maintitleNode == None:
            maintitleNode = titleNodes[0]

        if newTitle != None:
            maintitleNode.text = newTitle
            maintitleNode.tail = '\n'
        #if

        if newSubtitle == None:
            # no subtitle provided and file had one, delete it
            if subtitleNode != None:
                self.deleteNode(subtitleNode)
            #
        else:
            # subtitle provided, overwrite existing or create new one
            if subtitleNode == None:
                subtitleNode = ET.SubElement(self._metadataNode, '{%s}title' % Epub.NS['dc'])
            #if
            subtitleNode.text = newSubtitle
            subtitleNode.tail = '\n'
        #if
    #setTitle

    def setAuthor(self, newAuthors):
        authorNodes = self._xml.findall('ns0:metadata/dc:creator', namespaces=Epub.NS)
        if len(authorNodes) == 0:
            raise Exception("Can't find authors in metadata")
        #if

        index = list(self._metadataNode).index(authorNodes[0])
        # delete all existing authors first
        for node in authorNodes:
            self.deleteNode(node)
        #for

        # add new authors
        for i in range(len(newAuthors)):
            idName = f'creator{i+1:02}'
            nodes = list()
            newNode = ET.Element('{%s}creator' % Epub.NS['dc'], attrib={'id': idName})
            newNode.text = newAuthors[i]
            newNode.tail = '\n'
            self._metadataNode.insert(index, newNode)
            index += 1

            newNode = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'role', 'id': f'#{idName}'})
            newNode.text = 'aut'
            self._metadataNode.insert(index, newNode)
            index += 1

            if len(newAuthors) > 1:
                newNode = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'display-seq', 'id': f'#{idName}'})
                newNode.text = f'{i}'
                self._metadataNode.insert(index, newNode)
                index += 1
            #if
        #for
    #setAuthor

    def setSeriesInfo(self, seriesInfo):
        """Find <metadata> element and add series info at the end."""

        seriesTitle, seriesNumber = seriesInfo

        # add series info to metadata
        # <meta property="belongs-to-collection" id="c01">
        #     The Lord of the Rings
        # </meta>
        # <meta refines="#c01" property="collection-type">set</meta>
        # <meta refines="#c01" property="group-position">2</meta>
        if settings['epub3']:
            meta = ET.SubElement(self._metadataNode, 'meta', {'property': 'belongs-to-collection', 'id':'series0'})
            meta.text = seriesTitle
            meta = ET.SubElement(self._metadataNode, 'meta', {'refines': '#series0', 'property': 'collection-type'})
            meta.text = 'set'
            meta = ET.SubElement(self._metadataNode, 'meta', {'refines': '#series0', 'property': 'group-position'})
            meta.text = f'{seriesNumber}'
        #if

        # Add series info to metadata in Calibre format
        # <meta name="calibre:series" content="The Lord of the Rings"/>
        # <meta name="calibre:series_index" content="2"/>
        if settings['calibre']:
            meta = ET.SubElement(self._metadataNode, 'meta', {'name': 'calibre:series', 'content': seriesTitle})
            meta = ET.SubElement(self._metadataNode, 'meta', {'name': 'calibre:series_index', 'content': seriesNumber})
        #if
    #setSeriesInfo

#Epub


def handleParameters():
    desc = """Update series metadata in epub. By default it uses calibre metadata format.
Writes output to new .epub.new file."""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('filename', type=str, help='epub file')
    parser.add_argument('-m', '--metadata', action='store_true', help='Dump xml metadata')
    parser.add_argument('-i', '--info',  action='store_true', help='Print info about ebook')
    parser.add_argument('-s', '--series', nargs=2, help='Set series info (Ex: -s "Series Name" 2)', metavar=('NAME', 'NUMBER'))
    parser.add_argument('-t', '--title', type=str, help='Set title')
    parser.add_argument('-u', '--subtitle', type=str, help='Set subtitle')
    parser.add_argument('-a', '--author', nargs='+', help='Set author(s)')
    parser.add_argument('-c', '--calibre', action='store_true', help='use Calibre series metadata format (default)')
    parser.add_argument('-3', '--epub3', action='store_true', help='use EPUB3 series metadata format')
    args = parser.parse_args()
    return args


def parseSeries(series_data):
    """Series data is of the format "Name:number"""

    colon = series_data.rfind(':')
    if colon < 0:
        return series_data, None

    name = series_data[0:colon]
    number = series_data[colon+1:]
    return name, number
#


def main():
    args = handleParameters()

    epub = Epub(args.filename)
    epub.readFile()

    # only filename given, print info about file
    if len(sys.argv) == 2:
        epub.printInfo()
        return
    #if

    fileModified = False

    if args.epub3:
        settings['epub3'] = True
        settings['calibre'] = False
    #
    # if both -3 and -c are given, write both formats
    if args.calibre:
        settings['calibre'] = True
    #

    if args.series != None:
        epub.setSeriesInfo(args.series)
        fileModified = True
    #if

    if args.title != None or args.subtitle != None:
        epub.setTitle(args.title, args.subtitle)
        fileModified = True
    #if

    if args.author != None:
        epub.setAuthor(args.author)
        fileModified = True
    #if

    if args.info:      # -i
        epub.printInfo()
    #if
    if args.metadata:  # -m
        epub.printMetadata()
    #if

    if fileModified:
        epub.saveFile()
    #if
#main

if __name__ == "__main__":
    # execute only if run as a script
    main()
#if
