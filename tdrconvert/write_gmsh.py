
def write_MeshFormat(ofh):
    ofh.write('''$MeshFormat
2.2 0 8
$EndMeshFormat
''')

def write_PhysicalNames(ofh, PhysicalGroups):
    ofh.write('''$PhysicalNames\n''')
    ofh.write("%d\n" % len(PhysicalGroups))
    for name, group in PhysicalGroups.items():
        ofh.write('%d %d "%s"\n' % (group.dim, group.index, group.name))
    ofh.write('''$EndPhysicalNames\n''')

def write_Nodes(ofh, coordinates):
    ofh.write('$Nodes\n')
    ofh.write('%d\n' % len(coordinates))
    for i, v in enumerate(coordinates):
        ofh.write('%d ' % (i + 1,))
        ofh.write('%1.16g %1.16g %1.16g\n' % tuple(v))
    ofh.write('$EndNodes\n')

# info can be either boundary info or region info
def write_element_info(ofh, PhysicalGroups, either_info, index):
    for name, info in either_info.items():
        group = PhysicalGroups[name]
        # elm-type number-of-tags physical-tag elementary-tag mesh-partition
        tag_info = [group.etype, 2, group.index, group.index]
        tag_info_string = " ".join([str(x) for x in tag_info])
        for element in info.elements:
            ofh.write("%d %s " % (index, tag_info_string))
            element_nodes = " ".join([str(x) for x in element])
            ofh.write("%s\n" % (element_nodes))
            index += 1
    return index

def write_Elements(ofh, PhysicalGroups, region_info, boundary_info):
    num_region_elements =  sum([len(x.elements) for x in region_info.values()])
    num_boundary_elements = sum([len(x.elements) for x in boundary_info.values()])
    num_elements = num_region_elements + num_boundary_elements
    ofh.write('$Elements\n%d\n' % (num_elements,))

    index = 1
    index = write_element_info(ofh, PhysicalGroups, boundary_info, index)
    index = write_element_info(ofh, PhysicalGroups, region_info, index)
    ofh.write('$EndElements\n')

def get_physical_groups(device):
    regions = ds.get_region_list(device=device)
    contacts = ds.get_contact_list(device=device)
    interfaces = ds.get_interface_list(device=device)
    dim = ds.get_dimension(device=device)

    groups = {}
    index = 1
    for c in contacts:
        groups[c] = PhysicalGroup(dim=dim-1, name=c, index=index)
        index += 1
    for i in interfaces:
        groups[i] = PhysicalGroup(dim=dim-1, name=i, index=index)
        index += 1
    for r in regions:
        groups[r] = PhysicalGroup(dim=dim, name=r, index=index)
        index += 1

    return groups

def get_region_info(device):
    region_info = {}
    max_coordinate = -1
    regions = ds.get_region_list(device=device)

    for region in regions:
        node_to_coordinates = [int(i) for i in ds.get_node_model_values(device=device, region=region, name="coordinate_index")]
        elements = ds.get_element_node_list(device=device, region=region, reorder=True)
        region_info[region] = RegionInfo(node_to_coordinates=node_to_coordinates, elements=elements)

    return region_info

def get_boundary_info(device, region_info):
    contacts = ds.get_contact_list(device=device)
    interfaces = ds.get_interface_list(device=device)

    boundary_info = {}
    for contact in contacts:
        region = ds.get_region_list(device=device, contact=contact)[0]
        elements = ds.get_element_node_list(device=device, region=region, contact=contact, reorder=True)
        boundary_info[contact] = BoundaryInfo(transform_nodes_to_coordinates(region_info[region].node_to_coordinates, elements))

    for interface in interfaces:
        region = ds.get_region_list(device=device, interface=interface)[0]
        elements = ds.get_element_node_list(device=device, region=region, interface=interface,reorder=True)
        boundary_info[interface] = BoundaryInfo(transform_nodes_to_coordinates(region_info[region].node_to_coordinates, elements))
    return boundary_info

def get_coordinates(device, region_info):
    regions = ds.get_region_list(device=device)

    max_coordinate = -1
    for region in region_info.values():
        region_max_coordinate = max(region.node_to_coordinates)
        max_coordinate = max(max_coordinate, region_max_coordinate)

    coordinates = [None] * (max_coordinate + 1)

    # collection of coordinates
    axis_names = ['x', 'y', 'z']
    for region in regions:
        node_coordinates = region_info[region].node_to_coordinates
        axis = []
        for i in axis_names:
            axis.append(ds.get_node_model_values(device=device, region=region, name=i))

        axis_values = list(zip(*axis))
        for ic, rc in enumerate(node_coordinates):
            coordinates[rc] = axis_values[ic]

    return coordinates

def write_mesh(ofh, coordinates, PhysicalGroups, region_info, boundary_info):
    write_MeshFormat(ofh)
    write_PhysicalNames(ofh, PhysicalGroups)
    write_Nodes(ofh, coordinates)
    write_Elements(ofh, PhysicalGroups=PhysicalGroups, region_info=region_info, boundary_info=boundary_info)


def get_device_info(device):
    device_info = {}
    contact_info = {}
    region_info = {}
    interface_info = {}

    for c in ds.get_contact_list(device=device):
        region = ds.get_region_list(device=device, contact=c)[0]
        material = ds.get_material(device=device, contact=c)
        contact_info[c] = {
            'name'     : c,
            'region'   : region,
            'material' : material,
        }

    for i in ds.get_interface_list(device=device):
        region = ds.get_region_list(device=device, interface=i)
        interface_info[i] = {
            'name'     : i,
            'region0'   : region[0],
            'region1'   : region[1],
        }

    for r in ds.get_region_list(device=device):
        material = ds.get_material(device=device, region=r)
        region_info[r] = {
            'name'     : r,
            'material'   : material,
        }

    device_info = {
        'name': device,
        'regions': region_info,
        'contacts': contact_info,
        'interfaces': interface_info,
    }
    return device_info

def get_coordinate_strings(coordinates):
    coordinate_strings = [None] * len(coordinates)
    coordinate_strings = ["%g, %g, %g" % (i[0], i[1], i[2]) for i in coordinates]
    return coordinate_strings

def get_element_coordinate_strings(coordinate_strings, elements, values):
    # values are constant over element
    # element node indexes are 1 based
    element_strings = [None] * len(elements)
    if len(elements[0]) == 4:
        prefix = "SS" # scalar tetrahedron
        nnodes = 4
    elif len(elements[0]) == 3:
        prefix = "ST" # scalar triangle
        nnodes = 3
    elif len(elements[0]) == 2:
        prefix = "SL" # scalar line
        nnodes = 2

    for i, element in enumerate(elements):
        cstring = ", ".join([coordinate_strings[x-1] for x in element])
        vstring = ", ".join(["%g" % values[i]] * nnodes)
        element_strings[i] = "%s( %s) {%s};" % (prefix, cstring, vstring)

    return "\n".join(element_strings) + "\n"

def write_background_field(filename, values, all_info):
    coordinate_strings = get_coordinate_strings(all_info['coordinates'])
    with open(filename, 'w') as ofh:
        ofh.write('View "background mesh" {\n')
        for region, region_info in all_info['region_info'].items():
            elements = region_info.elements
            element_string = get_element_coordinate_strings(coordinate_strings, elements, values[region])
            ofh.write(element_string)
        ofh.write('};')

def write_gmsh_import(gmsh, gmsh_import, device_info):

    device_name = device_info['name']

    with open(gmsh_import, "w") as ofh:
        ofh.write('''\
import ds
ds.create_gmsh_mesh(file="%s", mesh="%s")
''' % (gmsh, device_name))
        for r in device_info["regions"].values():
            ofh.write('ds.add_gmsh_region(mesh="%s", gmsh_name="%s", region="%s", material="%s")\n' % (device_name, r["name"], r["name"], r["material"]))
        for i in device_info["interfaces"].values():
            ofh.write('ds.add_gmsh_interface(mesh="%s", gmsh_name="%s", name="%s", region0="%s", region1="%s")\n' % (device_name, i["name"], i["name"], i["region0"], i["region1"]))
        for c in device_info["contacts"].values():
            ofh.write('ds.add_gmsh_contact(mesh="%s", gmsh_name="%s", name="%s", region="%s", material="%s")\n' % (device_name, c["name"], c["name"], c["region"], c["material"]))
        ofh.write('ds.finalize_mesh(mesh="%s")\n' % (device_name,))
        ofh.write('ds.create_device(mesh="%s", device="%s")\n' % (device_name, device_name))

def write_gmsh(filename, all_info):
    coordinates = all_info['coordinates']
    groups      = all_info['groups']
    region_info = all_info['region_info']
    boundary_info = all_info['boundary_info']
    # write out the mesh
    with open(filename, "w") as ofh:
        write_mesh(ofh, coordinates=coordinates, PhysicalGroups=groups, region_info=region_info, boundary_info=boundary_info)

