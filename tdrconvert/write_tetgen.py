#http://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_node
# Node count, 3 dim, no attribute, no boundary marker
# Node index, node coordinates
def write_tetgen_nodes(ofh, coordinates):
    ofh.write("%d %d 0 0\n" % (len(coordinates), 3))
    for i, v in enumerate(coordinates):
        ofh.write('%d ' % (i + 1,))
        ofh.write('%1.16g %1.16g %1.16g\n' % tuple(v))

#http://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_ele
#First line: <# of tetrahedra> <nodes per tet. (4 or 10)> <region attribute (0 or 1)>
#  Remaining lines list # of tetrahedra:
#    <tetrahedron #> <node> <node> ... <node> [attribute]
def write_tetgen_elements(ofh, PhysicalGroups, region_info):
    num_region_elements =  sum([len(x.elements) for x in region_info.values()])
    ofh.write("%d 4 1\n" % (num_region_elements))
    index = 1
    for name, info in region_info.items():
        region_index = PhysicalGroups[name].index
        for element in info.elements:
            ofh.write('%d ' % index)
            ofh.write(' '.join([str(x) for x in element]))
            ofh.write(' %d\n' % region_index)
            index += 1


#http://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_face
# note that we can add the indexes of the tetrahedron on either side of the fac First line: <# of faces> <boundary marker (0 or 1)>
#  Remaining lines list # of faces:
#    <face #> <node> <node> <node> ... [boundary marker] ...e
def write_tetgen_faces(ofh, PhysicalGroups, boundary_info):
    num_boundary_elements =  sum([len(x.elements) for x in boundary_info.values()])
    ofh.write("%d 1\n" % (num_boundary_elements))
    index = 1
    for name, info in boundary_info.items():
        boundary_index = PhysicalGroups[name].index
        for element in info.elements:
            ofh.write('%d ' % index)
            ofh.write(' '.join([str(x) for x in element]))
            ofh.write(' %d\n' % boundary_index)
            index += 1

# http://wias-berlin.de/software/tetgen/1.5/doc/manual/manual006.html#ff_vol
def write_vol_file(filename, values, all_info):
    with open(filename, 'w') as ofh:
        out_values = []
        for region, region_info in all_info['region_info'].items():
            elements = region_info.elements
            out_values.extend(values[region])
        ofh.write('%d\n' % len(out_values))
        for i, v in enumerate(out_values):
            ofh.write('%d %g\n' % (i+1,v))

def write_tetgen(basename, all_info):
    coordinates = all_info['coordinates']
    groups      = all_info['groups']
    region_info = all_info['region_info']
    boundary_info = all_info['boundary_info']
    # write out the mesh
    with open(basename + '.node', 'w') as ofh:
        write_tetgen_nodes(ofh, coordinates)
    with open(basename + '.ele', 'w') as ofh:
        write_tetgen_elements(ofh, PhysicalGroups=groups, region_info=region_info)
    with open(basename + '.face', 'w') as ofh:
        write_tetgen_faces(ofh, PhysicalGroups=groups, boundary_info=boundary_info)

