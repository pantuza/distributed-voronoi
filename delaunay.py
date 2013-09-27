'''
Created on 22/09/2013

@author: Gustavo Pantuza
'''
from point2D import Point2D
from triangle import Triangle
from sys import maxint
from numpy.linalg import det

class Delaunay(object):
    '''
    Delaunay Triangulation
    ref: http://www.cs.cornell.edu/home/chew/Delaunay.html
    '''


    def __init__(self, inf = 2147483648):
        self._initTriangle = Triangle(Point2D(-inf, -inf), 
                                      Point2D(inf, -inf), 
                                      Point2D(0, inf))
        self.neighborhood = {self._initTriangle: {}}
        self.main_site = None
        self.main_triangle = None
        self.main_triangles = None
        self.main_points = None

    def __repr__(self):
        return 'Triangulation with ' + str(len(self.neighborhood)) + ' triangles'

    def __str__(self):
        return self.__repr__() 

    def add(self, site):
        '''
        Add a site to triangulation
        '''
        triangle = self._findTriangleCircumcircle(site)
        if not triangle.contains(site):
            cavity = self._getCavity(site, triangle)
            self._insert(site, cavity)
            self.main_triangles = None
            return True
        return False
    
    def addMainSite(self, site):
        '''
        Define a main site
        '''
        if self.add(site):
            self.main_site = site

    def _update_main_data(self):
        '''
        Check and update controls of "main site"
        '''
        if self.main_triangles is None:
            self.main_triangle = self._findTriangleContains(self.main_site)
            self.main_triangles, self.main_points = \
                    self.surroundingTriangles(self.main_site, 
                                              self.main_triangle)
    
    def clear_main_site(self):
        '''
        Remove all sites that do not affect a "main site" cell
        '''
        self._update_main_data()
        # search irrlevant sites
        dispensables = []
        for triangle in self.neighborhood:
            if (not triangle in self.main_triangle):
                dispensable = True
                for adjacent in self.main_points:
                    if triangle.contains(adjacent):
                        dispensable = False
                        break
                if dispensable:
                   dispensables.append(triangle)
        # remove irrlevant sites
        for triangle in dispensables:
            for site in triangle:
                if not self._initTriangle.contains(site):
                    try:
                        self.remove(site)
                    except:
                        pass
    
    
    def addSurrounding(self, site):
        '''
        Add a site only if it will affect a main site cell
        '''
        if self.main_site is None:
            # default add
            return self.add(site)
        else:
            # verify cache
            self._update_main_data()
            # verify site influence
            for triangle in self.main_triangles:
                if triangle.circumcircle(site):
                    return self.add(site)
            return False

    def remove(self, site):
        '''
        Remove a site from triagulation
        '''
        if (self.main_site is not None) and (site == self.main_site):
            return False
        triangle = self._findTriangleContains(site)
        if triangle is not None:
            triangles, points = self.surroundingTriangles(site, triangle)
            self._remove(site, points, triangles)
            self.main_triangles = None
            return True
        return False

    def _findTriangleCircumcircle(self, site):
        '''
        Search the triangle that circumcircle the point
        '''
        for triangle in self.neighborhood:
            if triangle.circumcircle(site) or triangle.contains(site):
                return triangle
        raise Exception("Site out of the valid area.")
    
    def _findTriangleContains(self, site):
        '''
        Search the triangle that contains the point
        '''
        for triangle in self.neighborhood.keys():
            if triangle.contains(site):
                return triangle
        raise Exception("Site does not exist:" + str(site))
    
    def _getCavity(self, site, triangle):
        '''
        Determine the cavity caused by site.
        '''
        encroached = {}
        toBeChecked = [triangle]
        marked = {triangle: None}
        while (len(toBeChecked) > 0):
            triangle = toBeChecked.pop()
            # Site outside triangle => triangle not in cavity
            if not triangle.circumcircle(site):
                continue
            encroached[triangle] = None
            # Check the neighborhood
            for neighbor in self.neighborhood[triangle]:
                if neighbor not in marked:
                    marked[neighbor] = None
                    toBeChecked.append(neighbor)
        return encroached

    def _addTriangle(self, t1, t2):
        if t1 not in self.neighborhood:
            self.neighborhood[t1] = {t2}
        else:
            self.neighborhood[t1][t2] = None

    def _delTriangle(self, triangle):
        del self.neighborhood[triangle]
        for neighbor in self.neighborhood.values():
            if triangle in neighbor:
                del neighbor[triangle]

    def _linkTriangles(self, t1, t2):
        self._addTriangle(t1, t2)
        self._addTriangle(t2, t1)

    def _insert(self, site, cavity):
        '''
        Update the triangulation by removing the cavity triangles and then
        filling the cavity with new triangles.
        '''
        boundary = {}
        triangles = {}

        # Find boundary facets and adjacent triangles
        for triangle in cavity:
            for neighbor in self.neighborhood[triangle]:
                # Adj triangles only
                if neighbor not in cavity:
                    triangles[neighbor] = None
            for point in triangle:
                facet = triangle.getOppositeFacet(point)
                if facet in boundary:
                    del boundary[facet]
                else:
                    boundary[facet] = None

        # Remove the cavity triangles from the triangulation
        for triangle in cavity:
            self._delTriangle(triangle)

        # Build each new triangle and add it to the triangulation
        newTriangles = {}
        for facet in boundary.keys():
            newTriangle = Triangle(facet[0], facet[1], site)
            self.neighborhood[newTriangle] = {}
            newTriangles[newTriangle] = None
            # Adj triangle + new triangles
            triangles[newTriangle] = None

        # Update the graph links for each new triangle
        for triangle in newTriangles:
            for other in triangles:
                if triangle.isNeighbor(other):
                    self._linkTriangles(triangle, other)

    def _remove(self, site, points, triangles):
        '''
        Update the triangulation by removing the surrounding triangles 
        and then filling this cavity with new Delaunay triangles.
        Challenge: Maintain neighborhood control.
        Ref: Mir Abolfazl Mostafavi, Christopher Gold, and Maciej Dakowicz. 
             2003. Delete and insert operations in Voronoi/Delaunay methods 
             and applications. Comput. Geosci. 29, 4 (May 2003), 523-530. 
             DOI=10.1016/S0098-3004(03)00017-7 
             http://dx.doi.org/10.1016/S0098-3004(03)00017-7
        '''
        # verify compatibility of lists of surrounding points and old triangles
        if len(points) != len(triangles):
            raise Exception("Current triangulation lists has different sizes.")
        # verify is the triangulation is empty (or insufficient?)
        if len(points) < 3:
            return
        # initialize new triangulation controls
        i = -1
        newTriangles = {}
        # while there are points to form more than the last triangle
        while len(points) > 3:
            # checks the possible triangles considering 
            # all three consecutive points (i, i1, i2 in a cycle) 
            # of surrounding points of the site
            i += 1
            npoints = len(points)
            if (i >= npoints):
                raise Exception("Inexists a valid ear? Is it possible?")
            i1 = i + 1
            if (i1 >= npoints):
                i1 -= npoints
            i2 = i + 2
            if (i2 >= npoints):
                i2 -= npoints
            # verify if points represent a valid triangle to site,
            # like a ear listen to the site:
            # 1: gets triangle direction (CW or CCW)
            direction1 = Triangle.determinant(points[i], points[i1], points[i2])
            # 2: gets direction of triangle to the site (CW or CCW)
            direction2 = Triangle.determinant(points[i], points[i2], site)
            # 3: if points are collinear, try another edge as a reference
            # ??why don't take this edge at first place??
            if direction2 == 0:
                direction2 = Triangle.determinant(points[i], points[i1], site)
            # 4: the directions is the same?
            if (direction1 * direction2) > 0:
                # if so, this a valid ear (possible triangulation)
                validEar = Triangle(points[i], points[i1], points[i2])
                # verify if this ear is a Delaunay Triangulation
                earIsDelaunay = True
                # 1. for all other surrounding points
                for p in points:
                    # 1.1: is this other point (not in ear)?
                    if not validEar.contains(p):
                        # verify if ear won't circumcircle it
                        if validEar.circumcircle(p):
                            # if circumcircle, ear is not a Delaunay triangle
                            earIsDelaunay = False
                            break
                # if it is a Delaunay triangle...
                if earIsDelaunay:
                    # add to new triangle control
                    newTriangles[validEar] = None
                    # add to neighborhood control
                    self.neighborhood[validEar] = {}
                    # link to the opposite triangles from the removed vertices
                    self._linkEar(site, validEar, triangles[i], newTriangles)
                    self._linkEar(site, validEar, triangles[i1], newTriangles)
                    # change triangle related to vertex by the new one
                    # remove old triangle by switching the diagonal
                    triangles[i] = validEar
                    # remove middle point (leave the corners) 
                    del points[i1]
                    del triangles[i1]
                    # restart cycle of surrounding points
                    i = -1
        # if has only three neighbours remaining in the surrounding points, 
        # merged these three points (triangles) into last triangulation
        lastEar = Triangle(points[0], points[1], points[2])
        self.neighborhood[lastEar] = {}
        newTriangles[lastEar] = None
        # last triangle closes the triangulation and 
        # needs update the link with all sides (neighborhood)
        self._linkEar(site, lastEar, triangles[0], newTriangles)
        self._linkEar(site, lastEar, triangles[1], newTriangles)
        self._linkEar(site, lastEar, triangles[2], newTriangles)

    def _linkEar(self, site, ear, triangle, newTriangles):
        # check if the triangle has neighbor that is opposite from the site
        neighbor = self.neighborOpposite(site, triangle)
        # if not, it's a external triangulation (connected to initial triangle) 
        # or it's a new triangulation...
        if neighbor is None:
            # if the triangle related to the vertex is new
            if triangle in newTriangles:
                # update neighborhood with the new triangle
                self._linkTriangles(ear, triangle)
            else:
                # otherwise, old triangle doesn't had a neighbor: 
                # ignore its neighborhood and delete it                
                self._delTriangle(triangle)
        else:
            # update neighborhood of new triangle (ear)
            self._linkTriangles(ear, neighbor)
            # delete old voronoi cell triangle
            self._delTriangle(triangle)

    def neighborOpposite(self, site, triangle):
        '''
        Report neighbor opposite the given vertex of triangle.
        '''
        if site not in triangle:
            return None
        for neighbor in self.neighborhood[triangle]:
            if not neighbor.contains(site):
                return neighbor
        return None

    def surroundingTriangles(self, site, triangle):
        '''
        Report triangles and points surrounding site in order (cw or ccw).
        '''
        if site not in triangle:
            raise Exception("Site not in triangle.")
        points = []
        triangles = []
        start = triangle
        # cw or cww (pay attention)
        guide = triangle.getNextVertexExcept({site})
        while triangle is not None:
            triangles.append(triangle)
            points.append(guide)
            previous = triangle
            triangle = self.neighborOpposite(guide, triangle)
            guide = previous.getNextVertexExcept({site, guide})
            if (triangle == start):
                break
        return triangles, points

    def getVoronoiCells(self):
        '''
        Report polygons of each voronoi cell
        '''
        cells = {}
        ignore = {x:None for x in self._initTriangle}
        for triangle in self.neighborhood.keys():
            for site in triangle:
                if site in ignore:
                    continue
                ignore[site] = None
                triangles, points = self.surroundingTriangles(site, triangle)
                cell = []
                for tri in triangles:
                    cell.append(tri.getCircumcenter())
                cells[site] = cell 
        return cells

    def getVoronoiCellTrinagulation(self, site):
        '''
        Test purpose only
        '''
        triangle = self._findTriangleContains(site)
        triangles, points = self.surroundingTriangles(site, triangle)
        return triangles, triangle

if __name__ == '__main__':

    v = Delaunay(1000)
    sites= [Point2D(100, 100),
            Point2D(150, 200),
            Point2D(300, 150),
            Point2D(250, 200)]
    for s in sites:
        v.add(s)
    print "DelaunayTriangulation created: Triangulation with " + \
        str(len(v.neighborhood)) + " triangles"
    c = 0
    for t in v.neighborhood:
        c += 1
        print str(c) + ":" + str(t)
        for n in v.neighborhood[t]:
            print "--> " + str(n)
    '''
    v2 = Delaunay(10)
    v2.add(Point2D(0,0))
    v2.add(Point2D(1,0))
    v2.add(Point2D(0,1))
    print "DelaunayTriangulation created: Triangulation with " + \
        str(len(v2.neighborhood)) + " triangles"
    c = 0
    for t in v2.neighborhood:
        c += 1
        print str(c) + ":" + str(t)
    '''
        
