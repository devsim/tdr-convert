import h5py
import numpy
import sys
from . import load_devsim as ds

compress_opts = {
    "compression" : "gzip",
}


def process_elements(data, Type):
    # a line
    if (data[0] == 1) and (numpy.unique(data[0::3]).shape[0] == 1):
        dimension = 1
    # a triangle
    elif (data[0] == 2) and (numpy.unique(data[0::4]).shape[0] == 1):
        dimension = 2
    # a tetrahedron 5
    elif (data[0] == 5) and (numpy.unique(data[0::5]).shape[0] == 1):
        dimension = 3
    else:
        raise RuntimeError("can't process elements")

    ename = get_shape_name(dimension)

    # the first and every dimension + 2 element after that is the element type
    new_array = numpy.delete(data, numpy.s_[0::dimension+2])
    # sort unique to get the coordinates indexes for region
    # this is a direct mapping for datasets later
    coordinates = numpy.unique(new_array)
    # reshape as table of coordinates indexes for a triangle or tetrahedron
    # -1 is the unknown
    new_array = numpy.reshape(new_array, (-1, dimension+1))

    ret = {
        'dim' : dimension,
        'coordinates' : coordinates,
        ename : new_array
    }
    return ret

def process_regions(geometry):
    nregions = geometry.attrs['number of regions']
    dimension = geometry.attrs['dimension']

    regions=[]
    for i in range(nregions):
        md = {}
        data = geometry['region_%d' % i]
        md['index'] = i
        md['hdf'] = data
        md['name'] = data.attrs['name'].decode('ascii')
        Type = data.attrs['type']
        if data.attrs['number of parts'] != 1:
            raise RuntimeError("Expecting only 1 part in region %d" % i)
        md['elements'] = process_elements(data['elements_0'][()], Type)
        #print md['elements']
        #0 bulk
        #1 contact
        #2 interface
        md['type'] = Type
        if Type == 0:
            md['typename'] = "region"
            md['material'] = data.attrs['material'].decode('ascii')
        elif Type == 1:
            md['typename'] = "contact"
            md['material'] = "metal"
            md['bulk 0'] = data.attrs['bulk 0']
        elif Type == 2:
            md['typename'] = "interface"
            md['bulk 0'] = data.attrs['bulk 0']

            md['bulk 1'] = data.attrs['bulk 1']

        else:
            raise RuntimeError("Can't process type %d" % Type)
        regions.append(md)
    return regions

def get_intersection_elements(intersection):
    '''
      Takes a set and returns a numpy array
    '''
    return numpy.array(sorted(intersection))

def remove_interfaces_at_contact(regions):
    '''
      get a list of all contact nodes and remove interfaces that contain them
    '''
    contacts = [x for x in regions if x['type'] == 1]
    all_contact_nodes = set([])
    for contact in contacts:
        surface_set = contact['surface_set']
        for i in surface_set:
            all_contact_nodes.update(i)

    interfaces = [x for x in regions if x['type'] == 2]
    for interface in interfaces:
        surface_set = interface['surface_set']
        new_set = set([])
        # i is the tuple of one surface element
        for i in surface_set:
            if all_contact_nodes.intersection(i):
                continue
            else:
                new_set.add(i)
        if not new_set:
            raise RuntimeError("Interface %s disappeared!" % (interface['name']))
        elif new_set != surface_set:
            interface['surface_set'] = new_set
            dim = interface['elements']['dim']
            shape_name = get_shape_name(dim)
            interface['elements'][shape_name] = get_intersection_elements(new_set)
            print("INTERFACE %s from %d to %d elements" % (interface['name'], len(surface_set), len(new_set)))


def split_contacts(regions, contact):
    contacts = []
    contact_surface = contact['surface_set']
    for region in regions:
        if region['type'] != 0:
            continue
        region_surface = region['surface_set']
        intersection = region_surface.intersection(contact_surface)
        if intersection:
            new_contact_name = contact['name'] + "_" + region['name']
            print("%s and %s intersect with %d elements!" % (region['name'], contact['name'], len(intersection)))
            print("Creating %s" % new_contact_name)
            c = {
                'name' : new_contact_name,
                'type' : 1,
                'typename' : 'contact',
                'material' : 'metal',
                'bulk 0' : region['index'],
                'bulk 0 name' : region['name'],
                'surface_set' : intersection,
            }
            dim = contact['elements']['dim']
            new_elements = get_intersection_elements(intersection)
            shape = get_shape_name(dim)
            c['elements'] =  {
                'dim' : dim,
                shape : new_elements,
            }
            contacts.append(c)
    return contacts

def update_boundary_regions(regions):
    contacts_to_add = []
    for r in regions:
        if r['type'] == 1:
            r0 = r['bulk 0']
            if is_contact_in_region(regions[r0], r):
                r['bulk 0 name'] = regions[r0]['name']
            else:
                print("bulk 0 reference %s for contact %s is not correct searching for proper connection" % (regions[r0]['name'], r['name']))
                found = False
                for r2 in regions:
                    if r2['type'] == 0:
                        if is_contact_in_region(r2, r):
                            r['bulk 0'] = r2['index']
                            r['bulk 0 name'] = r2['name']
                            print("bulk 0 reference for contact %s has been updated to %s" % (r['name'], r2['name']))
                            found = True
                            break
                if not found:
                    new_contacts = split_contacts(regions, r)
                    contacts_to_add.append((r['index'], new_contacts))
                    if not new_contacts:
                        raise RuntimeError("Could not find attachment for contact " + r['name'])
        elif r['type'] == 2:
            r0 = r['bulk 0']
            r1 = r['bulk 1']
            r['bulk 0 name'] = regions[r0]['name']
            r['bulk 1 name'] = regions[r1]['name']

    for c in contacts_to_add:
        index = c[0]
        contacts = c[1]
        regions[index] = contacts[0]
        regions[index]['index'] = index
        for i in contacts[1:]:
            index = len(regions)
            i['index'] = index
            regions.append(i)

def is_contact_in_region(region, contact_region):
    intersection = region['surface_set'].intersection(contact_region['surface_set'])
    if len(intersection) == len(contact_region['surface_set']):
        return True
    return False

def extract_surface_from_volume(region):
    '''
      find surface elements
    '''
    elements = region['elements']
    dim = elements['dim']
    if dim == 3:
        volume = elements['tetrahedra']
        surface_type = 'triangles'
    elif dim == 2:
        volume = elements['triangles']
        surface_type = 'edges'
    else:
        raise RuntimeError("ISSUE GETTING SURFACE")
    surface_dim = dim - 1

    surface = set([])
    duplicates = set([])
    new_elements = []
    for row in volume:
        nodes = sorted(list(row))
        if dim == 3:
            new_elements.append((nodes[0], nodes[1], nodes[2]))
            new_elements.append((nodes[0], nodes[1], nodes[3]))
            new_elements.append((nodes[0], nodes[2], nodes[3]))
            new_elements.append((nodes[1], nodes[2], nodes[3]))
        elif dim == 2:
            new_elements.append((nodes[0], nodes[1]))
            new_elements.append((nodes[0], nodes[2]))
            new_elements.append((nodes[1], nodes[2]))

    for n in new_elements:
        if n in duplicates:
            continue
        elif n in surface:
            surface.remove(n)
            duplicates.add(n)
        else:
            surface.add(n)

    region['surface_set'] = surface

def extract_surface_from_contact(region):
    elements = region['elements']
    dim = elements['dim']
    surface_type = get_shape_name(dim)
    shapes = elements[surface_type]
    surface = []
    for row in shapes:
        surface.append(tuple(sorted(list(row))))

    region['surface_set'] = set(surface)


def get_shape_name(dim):
    if dim == 3:
        return 'tetrahedra'
    elif dim == 2:
        return 'triangles'
    elif dim == 1:
        return 'edges'
    elif dim == 0:
        return 'points'

    raise RuntimeError("Issue getting shape name from dimension")

def find_interfaces(regions):
    interfaces = []
    rlist = [r for r in regions if r['typename']=="region"]
    for i in range(len(rlist)-1):
        r0 = rlist[i]['surface_set']
        dim = rlist[i]['elements']['dim']
        for j in range(i+1, len(rlist)):
            r1 = rlist[j]['surface_set']
            k = r0.intersection(r1)
            if k:
                print("intersection of %s and %s" % (rlist[i]['name'], rlist[j]['name']))


                interfaces.append({
                    'name' : rlist[i]['name'] + '_' + rlist[j]['name'],
                    'type' : 2,
                    'typename' : 'interface',
                    'bulk 0' : rlist[i]['index'],
                    'bulk 0 name' : rlist[i]['name'],
                    'bulk 1' : rlist[j]['index'],
                    'bulk 1 name' : rlist[j]['name'],
                    'surface_set' : k,
                    'elements' : {
                        'dim' : dim - 1,
                        get_shape_name(dim-1) : get_intersection_elements(k)
                    }
                })
    return interfaces

def get_elements(region):
    elements = region['elements']
    physical_index = region['physical_index']
    out_elements = []
    if "tetrahedra" in elements:
        for i in elements['tetrahedra']:
            out_elements.extend((3, physical_index, int(i[0]), int(i[1]), int(i[2]), int(i[3])))
    elif "triangles" in elements:
        for i in elements['triangles']:
            out_elements.extend((2, physical_index, int(i[0]), int(i[1]), int(i[2])))
    elif "edges" in elements:
        for i in elements['edges']:
            out_elements.extend((1, physical_index, int(i[0]), int(i[1])))
    elif "points" in elements:
        for i in elements['points']:
            out_elements.extend((0, physical_index, int(i)))
    return out_elements

def write_region(region):
    out_elements = get_elements(region)
    return {
        'name' : region['name'],
        'material' : region['material'],
        'elements' : out_elements,
    }

def write_contact(contact):
    out_elements = get_elements(contact)
    return {
        'name' : contact['name'],
        'region' : contact['bulk 0 name'],
        'material' : contact['material'],
        'elements' : out_elements,
    }

def write_interface(interface):
    out_elements = get_elements(interface)
    return {
        'name' : interface['name'],
        'region0' : interface['bulk 0 name'],
        'region1' : interface['bulk 1 name'],
        'elements' : out_elements,
    }

def get_coordinates(vertex,scale):
    coordinates = []
    # TODO: optimize
    if len(vertex.dtype) == 2:
        for i in vertex:
            coordinates.extend((float(i[0])*scale, float(i[1])*scale, 0.0))
    elif len(vertex.dtype) == 3:
        for i in vertex:
            coordinates.extend((float(i[0])*scale, float(i[1])*scale, float(i[2])*scale))
    else:
        raise RuntimeError("Unexpected Dimension")
    coordinates = numpy.array(coordinates)
    return coordinates

def write_devsim(regions):
    out_regions = [x for x in regions if x["type"] == 0]
    for r in out_regions:
        r['out_info'] = write_region(r)


    out_contacts = [x for x in regions if x["type"] == 1]
    for c in out_contacts:
        c['out_info'] = write_contact(c)

    out_interfaces = [x for x in regions if x["type"] == 2]
    for i in out_interfaces:
        i['out_info'] = write_interface(i)

def read_tdr(filename, scale, drop_interfaces_at_contact):
    f = h5py.File(filename)
    #print(list(f.keys()))
    collection=f['collection']
    #print(list(collection.attrs.keys()))
    geometry=collection['geometry_0']
    dimension = geometry.attrs['dimension']

    # this is the coordinate data
    vertex = geometry['vertex']
    if len(vertex.dtype) == 3:
        vertex=vertex['x', 'y', 'z']
    else:
        vertex=vertex['x', 'y']
    coordinates = get_coordinates(vertex, scale)

    regions = process_regions(geometry)

    for r in regions:
        if r['type'] == 0:
            extract_surface_from_volume(r)
        else:
            extract_surface_from_contact(r)

    update_boundary_regions(regions)


    # create interfaces
    # this is only if interfaces don't exist in regions
    if not [x for x in regions if x['type'] == 2]:
        print("no interfaces present, searching")
        interfaces = find_interfaces(regions)
        for i in interfaces:
            i['index'] = len(regions)
            regions.append(i)

    if drop_interfaces_at_contact:
        remove_interfaces_at_contact(regions)

    for i, j in enumerate(regions):
        j['physical_index'] = i

    # process all of the elements
    write_devsim(regions)

    physical_names = [x['name'] for x in regions]

    elements = []
    for i in regions:
        elements.extend(i['out_info']['elements'])

    return {
        'coordinates' : coordinates,
        'physical_names' : physical_names,
        'elements' : elements,
        'regions' : regions,
        'geometry' : geometry,
        'dimension' : dimension,
    }

def create_devsim_mesh(mesh, data):
    coordinates=data['coordinates']
    regions=data['regions']
    elements=data['elements']
    physical_names=data['physical_names']

    ds.create_gmsh_mesh(mesh=mesh, coordinates=coordinates, physical_names=physical_names, elements=elements)
    for r in regions:
        if r['typename'] == 'region':
            name = r['name']
            material = r['material']
            ds.add_gmsh_region(mesh=mesh, region=name, gmsh_name=name, material=material)
    for region in regions:
        if region['typename'] == 'contact':
            name = region['name']
            material = region['material']
            region_name = region['bulk 0 name']
            ds.add_gmsh_contact(mesh=mesh, name=name, gmsh_name=name, material=material, region=region_name)
        elif region['typename'] == 'interface':
            name = region['name']
            region0_name = region['bulk 0 name']
            region1_name = region['bulk 1 name']
            ds.add_gmsh_interface(mesh=mesh, name=name, gmsh_name=name, region0=region0_name, region1=region1_name)
        elif region['typename'] != 'region':
            raise RuntimeError("UNEXPECTED TYPENAME")
    ds.finalize_mesh(mesh=mesh)

def create_node_solution(device, region, name, values):
    ds.node_solution(device=device, region=region, name=name)
    if numpy.unique(values).shape[0] == 1:
        v=values[0]
        ds.set_node_value(device=device, region=region, name=name, value=v)
    else:
        #v=[float(x) for x in values]
        ds.set_node_values(device=device, region=region, name=name, values=values)

def load_datasets(data):
    print("Loading data")
    datasets = []
    state = data['geometry']['state_0']
    for n, d in list(state.items()):
        # skip non data sets
        if n.find('dataset') != 0:
            continue
        name   = d.attrs['name'].decode('ascii')
        region = d.attrs['region']
        # skip non regions (interfaces, contacts)
        region_type = data['regions'][region]['type']
        if region_type != 0:
            rname=data['regions'][region]['name']
            #print(f'Skip loading data for {name} {rname} of type {region_type}')
            continue
        values = d['values'][()]
        structure_type = d.attrs['structure type']
        location_type = d.attrs['location type']
        number_of_values = d.attrs['number of values']
        number_of_rows = d.attrs.get('number of rows', 1)
        # skip non scalar fields for now
        if location_type == 0 and structure_type in (0,1,):
            # structure_type:
                # 0 if scalar
                # 1 if vector
            edict = data['regions'][region]['elements']
            nnode = len(edict['coordinates'])

            if nnode != (len(values) // number_of_rows):
                raise RuntimeError(number_of_rows)

            values = numpy.transpose(values.reshape(-1, number_of_rows))
            datasets.append(
                {
                    'name' : name,
                    'region' : region,
                    'values' : values,
                    'dataset' : n,
                    'nrows' : number_of_rows,
                }
            )
            rname=data['regions'][region]['name']
            edict = data['regions'][region]['elements']
            nnode = len(edict['coordinates'])
            sname = get_shape_name(edict['dim'])
            nele = len(edict[sname])
#            print(f'''Loading data for {name} {rname} {n}''')
#            print(f'''Loading data for {name} {rname} {n}
#    region {rname} has {nnode} nodes and {nele} {sname}
#    {n} has {len(values)} values with {number_of_rows} rows
#    structure {structure_type} location {location_type} type {region_type}''')
        else:
            rname=data['regions'][region]['name']
            edict = data['regions'][region]['elements']
            nnode = len(edict['coordinates'])
            sname = get_shape_name(edict['dim'])
            nele = len(edict[sname])
            print(f'''Skipping data for {name} {rname} {n}
    region {rname} has {nnode} nodes and {nele} {sname}
    {n} has {len(values)} values
    structure {structure_type} location {location_type} type {region_type}''')
    return datasets


def create_devsim_data(device_name, data, datasets):
    for d in datasets:
        r=data['regions'][d['region']]['name']
        n=d['name']
        v=d['values']
        nrows = d['nrows']

        if nrows == 1:
            create_node_solution(device=device_name, region=r, name=n, values=v)
        else:
            for i in range(nrows):
                create_node_solution(device=device_name, region=r, name=f'{n}_{i}', values=v[i,:])

