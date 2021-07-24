#!/usr/bin/env python

import argparse
import zipfile
import xml.etree.ElementTree as ET
import re


settings = {'epub3': False,
            'calibre': True
            }

NS = {'ns0': 'http://www.idpf.org/2007/opf',
      'dc': 'http://purl.org/dc/elements/1.1/'}


def handleParameters():
    desc = """Update series metadata in epub. By default it uses calibre metadata format.
Writes output to new .epub.new file."""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('seriesinfo', type=str, help='Series info with format "Series Name:2"')
    parser.add_argument('filename', type=str, help='epub file')
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


def findContent(zfile):
    """Find location of 'content.opf' file. This is stored in 'META-INF/container.xml'"""
    with zfile.open("META-INF/container.xml") as file:
        xml = ET.fromstring(file.read())
    #with

    return xml[0][0].attrib['full-path']        # <container> <rootfiles> <rootfile full-path="...">
#findContent

def printMetadata(xml):
    metadata = xml.find('ns0:metadata', namespaces=NS)
    if metadata == None:
        raise Exception("Can't find metadata object")
    #
    title = metadata.find('dc:title', namespaces=NS)
    authors = [a.text for a in metadata.findall('dc:creator', namespaces=NS)]

    print('Title: {}'.format(title.text))
    print('Author: {}'.format(", ".join(authors)))

    calName_ele = metadata.find("meta[@name='calibre:series']")
    calNumber_ele = metadata.find("meta[@name='calibre:series_index']")
    calName = calName_ele.attrib['content'] if calName_ele!=None else ''
    calNumber = calNumber_ele.attrib['content'] if calNumber_ele!=None else ''

    epub3Name_ele = metadata.find("meta[@property='belongs-to-collection']")
    epub3Number = ''
    if epub3Name_ele:
        seriesId = epub3Name_ele.attrib['id']
        epub3Number_ele = metadata.find("meta[@refines='{}']".format(seriesId))
        epub3Number = epub3Number_ele.text if epub3Number_ele!=None else ''
    #fi
    epub3Name = epub3Name_ele.text if epub3Name_ele!=None else ''

    if len(calName) > 0:
        print("Series: {} : {}  (calibre)".format(calName, calNumber))
    #if
    if len(epub3Name) > 0:
        print("Series: {} : {}  (calibre)".format(epub3Name, epub3Number))
    #if

#printMetadata


def addSeriesToMetadata(xml, series_title, series_number):
    """Find <metadata> element and add series info at the end."""

    # extract namespace from root element
    namespace = re.match(r'{.*}', xml.tag).group(0)  # namespace='{http://www.idpf.org/2007/opf}'
    ns = {'root': namespace[1:-1]}   # without the { }
    # now we can find the 'metadata' object
    metadata = xml.find('root:metadata', ns)
    if metadata == None:
        raise Exception("Can't find metadata object")
    #

    # add series info to metadata
    # <meta property="belongs-to-collection" id="c01">
    #     The Lord of the Rings
    # </meta>
    # <meta refines="#c01" property="collection-type">set</meta>
    # <meta refines="#c01" property="group-position">2</meta>
    if settings['epub3']:
        meta = ET.SubElement(metadata, 'meta', {'property': 'belongs-to-collection', 'id':'series0'})
        meta.text = series_title
        meta = ET.SubElement(metadata, 'meta', {'refines': '#series0', 'property': 'collection-type'})
        meta.text = 'set'
        meta = ET.SubElement(metadata, 'meta', {'refines': '#series0', 'property': 'group-position'})
        meta.text = f'{series_number}'

    # Add series info to metadata in Calibre format
    # <meta name="calibre:series" content="The Lord of the Rings"/>
    # <meta name="calibre:series_index" content="2"/>
    if settings['calibre']:
        meta = ET.SubElement(metadata, 'meta', {'name': 'calibre:series', 'content': series_title})
        meta = ET.SubElement(metadata, 'meta', {'name': 'calibre:series_index', 'content': series_number})
#


def updateZipFile(zip_filename, content_filename, xml):
    elem_tree = ET.ElementTree(xml)

    new_zip_filename = zip_filename + '.new'
    # create a temp copy of the archive without filename
    with zipfile.ZipFile(zip_filename, 'r') as zin:
        with zipfile.ZipFile(new_zip_filename, 'w') as zout:
            zout.comment = zin.comment # preserve the comment
            for item in zin.infolist():
                if item.filename != content_filename:
                    zout.writestr(item, zin.read(item.filename))
                #
            #for
        #with
    #with

    with zipfile.ZipFile(new_zip_filename, 'a', compression=zipfile.ZIP_DEFLATED) as zout:
        with zout.open(content_filename, 'w') as file:
            elem_tree.write(file)
        #
    #
    print(f"New epub file: '{new_zip_filename}'")
#

def deleteRefines(metadataNode, idName):
    if idName == None:
        return

    for refineNode in metadataNode.findall(f'.//*[@refines="#{idName}"]'):
        metadataNode.remove(refineNode)
    #if
#deleteRefines

def setTitle(xml, newTitle):
    metadata = xml.find('ns0:metadata', namespaces=NS)
    oldTitles = xml.findall('ns0:metadata/dc:title', namespaces=NS)
    if metadata == None or len(oldTitles) == 0:
        raise Exception("Can't find title in metadata")
    #

    if len(oldTitles) > 1:
        print(f'WARNING: found {len(oldTitles)} in metadata section')
    #if

    # delete old title(s)
    nodeIndex = list(metadata).index(oldTitles[0])
    for titleNode in oldTitles:
        # delete any nodes that refine this title
        titleId = titleNode.attrib['id'] if 'id' in titleNode.attrib else None
        deleteRefines(metadata, titleId)

        # delete title node
        metadata.remove(titleNode)
    #for

    titleNode = ET.Element('{%s}title' % NS['dc'])
    titleNode.text = newTitle
    titleNode.tail = '\n'
    metadata.insert(nodeIndex, titleNode)
#setTitle

def setAuthor(xml, newAuthors):
    metadata = xml.find('ns0:metadata', namespaces=NS)
    oldAuthors = xml.findall('ns0:metadata/dc:creator', namespaces=NS)
    if metadata == None or len(oldAuthors) == 0:
        raise Exception("Can't find authors in metadata")
    #

    # delete old authors
    nodeIndex = list(metadata).index(oldAuthors[0])
    for authorNode in oldAuthors:
        # delete any nodes that refine this author: with attrib refines="#creator01"
        authorId = authorNode.attrib['id'] if 'id' in authorNode.attrib else None
        deleteRefines(metadata, authorId)

        # delete author node
        metadata.remove(authorNode)
    #for

    # add new authors
    for i in range(len(newAuthors)):
        authorId = f'creator{(i+1):02}'
        authorName = newAuthors[i]
        authorNode = ET.Element('{%s}creator' % NS['dc'], attrib={'id': authorId})
        authorNode.text = authorName
        authorNode.tail = '\n'
        metadata.insert(nodeIndex, authorNode)
        nodeIndex += 1

        metaNode = ET.Element('{%s}meta' % NS['ns0'], attrib={'id': 'role', 'refines': f'#{authorId}'})
        metaNode.text = 'aut'
        metaNode.tail = '\n'
        metadata.insert(nodeIndex, metaNode)
        nodeIndex += 1
    #for
#setAuthor

def main():
    args = handleParameters()
    epub_filename = args.filename
    series_title, series_number = parseSeries(args.seriesinfo)

    if args.epub3:
        settings['epub3'] = True
        settings['calibre'] = False
    #
    # if both -3 and -c are given, write both formats
    if args.calibre:
        settings['calibre'] = True
    #

    if series_number == None:
        print(f"ERROR: couldn't parse series info: '{args.series}'")
        return
    #

    try:
        zfile = zipfile.ZipFile(epub_filename)
        content_filename = findContent(zfile)
        #print(f"Found: {content_filename}")
    except FileNotFoundError:
        print(f"ERROR: File '{epub_filename}' not found. Bailing out.")
        return
    #try

    with zfile.open(content_filename) as file:
        xml = ET.fromstring(file.read())
    #with
    zfile.close()


    addSeriesToMetadata(xml, series_title, series_number)

    updateZipFile(epub_filename, content_filename, xml)
#



if __name__ == "__main__":
    # execute only if run as a script
    main()
#if
