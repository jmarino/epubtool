#!/usr/bin/env python

import argparse
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import re
import copy
import sys


#**TODO** remove old series info before adding new one
#**TODO** store fileModified inside Epub class

settings = {'epub3': False,
            'calibre': True
            }


class Epub:
    # Namespaces
    NS = {'ns0': 'http://www.idpf.org/2007/opf',
          'dc': 'http://purl.org/dc/elements/1.1/'}

    def __init__(self, fileName):
        self._fileName = Path(fileName)
        self._contentFileName = None
        self._xml = None               # ElementTree main object
        self._metadataNode = None      # metadata node
        self._version = None
        self._fileModified = False
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
        if self._fileModified == False:
            return

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
        titleNodes = self._metadataNode.findall('./dc:title', namespaces=Epub.NS)
        for node in titleNodes:
            refinesNode = self.findRefines(node, 'title-type')
            if refinesNode == None:
                title = node.text
            else:
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

    def getSeries(self):
        # check for epub3 series info
        nameNode = self._metadataNode.find("./meta[@property='belongs-to-collection']")
        if nameNode == None:
            nameNode = self._metadataNode.find("./ns0:meta[@property='belongs-to-collection']", namespaces=Epub.NS)
        #if
        refines = self.findRefines(nameNode, 'group-position')
        if refines != None:
            name = nameNode.text
            number = refines.text
            return name, number, 'epub3'
        #if

        # check for calibre series info
        nameNode = self._metadataNode.find("./meta[@name='calibre:series']")
        if nameNode == None:
            nameNode = self._metadataNode.find("./ns0:meta[@name='calibre:series']", namespaces=Epub.NS)
        #if
        numberNode = self._metadataNode.find("./meta[@name='calibre:series_index']")
        if numberNode == None:
            numberNode = self._metadataNode.find("./ns0:meta[@name='calibre:series_index']", namespaces=Epub.NS)
        #if
        if nameNode == None or numberNode == None or \
           not 'content' in nameNode.attrib or not 'content' in numberNode.attrib:
            return None, None, None
        #

        name = nameNode.attrib['content']
        number = numberNode.attrib['content']
        return name, number, 'Calibre'
    #getSeries

    def printInfo(self):
        title, subtitle = self.getTitle()
        authors = self.getAuthors()

        print(f'File:\t{self._fileName.name} (epub {self._version})')
        print(f'Info:\t', end="")
        if subtitle == None:
            print(f'"{title}"')
        else:
            print(f'"{title}: {subtitle}"')

        if len(authors) == 1:
            print(f'\t{authors[0]}')
        else:
            authorsStr = ", ".join(authors)
            print(f'\t{authorsStr}')
        #if

        seriesName, seriesNumber, source = self.getSeries()
        if seriesName != None and seriesNumber != None:
            print(f"Series:\t{seriesName} : {seriesNumber}  ({source})")
        #if
        print()
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
        """Set title and/or subtitle.
        The way we do this is: extract all title elements and their refines from the document.
        - Only title is provided: create a new title and add it, no refines
        - Only subtitle is provided: reuse title and add subtitle, setting 2 refines each: 'title-type' and 'display-seq'
        - Both provided: set title and subtitle, setting 2 refines each
        """

        if newTitle == None and newSubtitle == None:
            return

        # Locate title nodes (and their refines) and extract title and subtitle
        oldTitle = None
        oldSubtitle = None
        metaNodes = list(self._metadataNode)
        firstIndex = len(metaNodes)
        titleNodes = list()
        for node in self._metadataNode.findall('./dc:title', namespaces=Epub.NS):
            titleNodes.append(node)
            firstIndex = min(firstIndex, metaNodes.index(node))
            idName = node.attrib['id'] if ('id' in node.attrib) else None
            if idName == None:
                oldTitle = node.text
                continue
            for refines in self._metadataNode.findall(f'./*[@refines="#{idName}"]'):
                titleNodes.append(refines)
                firstIndex = min(firstIndex, metaNodes.index(refines))

                if ('property' in refines.attrib) and (refines.attrib['property'] == 'title-type'):
                    if refines.text == 'main':
                        oldTitle = node.text
                    elif refines.text == 'subtitle':
                        oldSubtitle = node.text
                    #if
                #if
            #for refines
        #for title nodes

        # delete title nodes and refines
        for node in titleNodes:
            self._metadataNode.remove(node)
        #for

        firstIndex = max(firstIndex, 0)

        # add new title item
        titleId = 'maintitle'
        node = ET.Element('{%s}title' % Epub.NS['dc'], attrib={'id': f'{titleId}'})
        node.text = newTitle if (newTitle != None) else oldTitle
        node.tail = '\n'
        self._metadataNode.insert(firstIndex, node)
        node = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'title-type', 'refines': f'#{titleId}'})
        node.text = 'main'
        node.tail = '\n'
        self._metadataNode.insert(firstIndex+1, node)
        node = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'display-seq', 'refines': f'#{titleId}'})
        node.text = '1'
        node.tail = '\n'
        self._metadataNode.insert(firstIndex+2, node)
        firstIndex += 3

        if newSubtitle != None:
            titleId = 'subtitle'
            node = ET.Element('{%s}title' % Epub.NS['dc'], attrib={'id': f'{titleId}'})
            node.text = newSubtitle
            node.tail = '\n'
            self._metadataNode.insert(firstIndex, node)
            node = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'title-type', 'refines': f'#{titleId}'})
            node.text = 'subtitle'
            node.tail = '\n'
            self._metadataNode.insert(firstIndex+1, node)
            node = ET.Element('{%s}meta' % Epub.NS['ns0'], attrib={'property': 'display-seq', 'refines': f'#{titleId}'})
            node.text = '2'
            node.tail = '\n'
            self._metadataNode.insert(firstIndex+2, node)
        #if
        self._fileModified = True
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
        self._fileModified = True
    #setAuthor

    def setSeriesInfo(self, seriesInfo):
        """Set series info. Parameter seriesInfo is an array: [seriesName, numberInSeries]"""

        # find any previous epub3 or calibre series info and delete it
        seriesNodes = self._metadataNode.findall('./meta[@property="belongs-to-collection"]') + \
            self._metadataNode.findall('./ns0:meta[@property="belongs-to-collection"]', namespaces=Epub.NS) + \
            self._metadataNode.findall('./ns0:meta[@name="calibre:series"]', namespaces=Epub.NS) + \
            self._metadataNode.findall('./meta[@name="calibre:series"]') + \
            self._metadataNode.findall('./ns0:meta[@name="calibre:series_index"]', namespaces=Epub.NS) + \
            self._metadataNode.findall('./meta[@name="calibre:series_index"]')
        for node in seriesNodes:
            self.deleteNode(node)
        #for

        if settings['epub3']:
            self.setSeriesInfoEpub3(seriesInfo)
        #if

        if settings['calibre']:
            self.setSeriesInfoCalibre(seriesInfo)
        #if
    #setSeriesInfo

    def setSeriesInfoEpub3(self, seriesInfo):
        seriesTitle, seriesNumber = seriesInfo

        # add epub3 series info to metadata
        #   <ns0:meta property="belongs-to-collection" id="c01">The Lord of the Rings</ns0:meta>
        #   <ns0:meta refines="#c01" property="collection-type">set</ns0:meta>
        #   <ns0:meta refines="#c01" property="group-position">2</ns0:meta>
        idName = 'series0'
        meta = ET.SubElement(self._metadataNode, '{%s}meta' % Epub.NS['ns0'], \
                             attrib={'property': 'belongs-to-collection', 'id': idName})
        meta.text = seriesTitle
        meta.tail = '\n'
        meta = ET.SubElement(self._metadataNode, '{%s}meta' % Epub.NS['ns0'], \
                             attrib={'property': 'collection-type', 'refines': f'#{idName}'})
        meta.text = 'series'
        meta.tail = '\n'
        meta = ET.SubElement(self._metadataNode, '{%s}meta' % Epub.NS['ns0'], \
                             attrib={'property': 'group-position', 'refines': f'#{idName}'})
        meta.text = f'{seriesNumber}'
        meta.tail = '\n'
        self._fileModified = True
    #setSeriesInfoEpub3

    def setSeriesInfoCalibre(self, seriesInfo):
        seriesTitle, seriesNumber = seriesInfo

        # Add series info to metadata in Calibre format
        #   <meta name="calibre:series" content="The Lord of the Rings"/>
        #   <meta name="calibre:series_index" content="2"/>
        meta = ET.SubElement(self._metadataNode, '{%s}meta' % Epub.NS['ns0'], {'name': 'calibre:series', 'content': seriesTitle})
        meta.tail = '\n'
        meta = ET.SubElement(self._metadataNode, '{%s}meta' % Epub.NS['ns0'], {'name': 'calibre:series_index', 'content': seriesNumber})
        meta.tail = '\n'
        self._fileModified = True
    #setSeriesInfoCalibre

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
    #if

    if args.title != None or args.subtitle != None:
        epub.setTitle(args.title, args.subtitle)
    #if

    if args.author != None:
        epub.setAuthor(args.author)
    #if

    if args.info:      # -i
        epub.printInfo()
    #if
    if args.metadata:  # -m
        epub.printMetadata()
    #if

    epub.saveFile()
#main

if __name__ == "__main__":
    # execute only if run as a script
    main()
#if
