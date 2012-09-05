#!/usr/bin/env python2
"""
sitegen.py is a static site generator for arun.chagantys.org
"""

import os
import git
import time
import string
import mimetypes
import logging
import subprocess as sp
import ConfigParser as CP
import itertools as it
PANDOC_EXTN = ".md"

import pdt
cal = pdt.Calendar() # Using PDT for robust date parsing.

pexists = os.path.exists
pjoin = os.path.join
dirname = os.path.dirname
basename = os.path.basename

mimetypes.add_type( "text/markdown", PANDOC_EXTN )

def get_date( fmts, data ):
    """Try to get the date by sequentially matching patterns"""
    # First try strptime
    for fmt in fmts:
        try:
            return time.strptime( fmt, data )
        except ValueError:
            pass
    try:
        return time.strptime( data )
    except ValueError:
        pass

    # Then try PDT
    try:
        return time.struct_time( cal.parseDateText( data ) )
    except AttributeError:
        pass
    except KeyError:
        pass

    raise ValueError

class ChangeSet:
    """Store set of changes"""
    def __init__( self, rev, modifys, deletes ):
        """Set of modifications and deletes"""
        self.rev = rev
        self.modifys = set( modifys )
        self.deletes = set( deletes )

    @staticmethod
    def from_diffiter( rev, diffs ):
        """Create a change set from a DiffIter"""
        return ChangeSet( rev,
                map( lambda d: d.b_blob, it.chain( 
                    diffs.iter_change_type('A'),
                    diffs.iter_change_type('M'),
                    diffs.iter_change_type('R') ) ),
                map( lambda d: d.a_blob, it.chain( 
                    diffs.iter_change_type('R'),
                    diffs.iter_change_type('D') ) )
                )

    @staticmethod
    def from_repo( repo ):
        """Create a basic change set from a Repo"""
        adds = filter(lambda x: isinstance(x, git.Blob),
                repo.tree().traverse()) 
        return ChangeSet( None, adds, [] )

    def __len__( self ):
        return len( self.modifys ) + len( self.deletes )

    def filter( self, base ):
        """Filter all changes from sets for this basename"""
        # Ignore trailing and leading /
        base = base.strip().strip("/")
        modifys = filter( lambda b: dirname( b.path ) == base,
                self.modifys)
        deletes = filter( lambda b: dirname( b.path ) == base,
                self.deletes)

        return ChangeSet( self.rev, modifys, deletes )

    def __sub__( self, cs ):
        """Subtract another diff from this"""
        return ChangeSet( self.rev, 
                self.modifys - cs.modifys, 
                self.deletes - cs.deletes
                )

    def pop( self, base ):
        """Extract the change set corresponding to this base"""
        cs = self.filter(base)
        self -= cs
        return cs

    def exists( self, path ):
        """Extract the change set corresponding to this base"""
        return path in self.modifys or path in self.deletes 

class SiteGenerator:
    """Static Site Generator"""
    REV_NAME = "current" 

    def __init__(self, conf_path):
        """Create a site generator with settings in the conf file"""
        self.conf = CP.ConfigParser()
        self.conf.read( conf_path )

        # Handle paths
        incoming_path = self.conf.get( "paths", "incoming" )
        if not pexists( incoming_path ):
            raise ValueError( "%s does not exist"% incoming_path )
        self.repo = git.Repo( incoming_path )

        self.meta_path = self.conf.get( "paths", "meta" )
        if not pexists( self.meta_path ):
            os.makedirs( self.meta_path )
        self.outgoing_path = self.conf.get( "paths", "outgoing" )

        # Construct template dict
        self.variables = dict( self.conf.items( "variables" ) )

        # Configure the logger 
        FORMAT = '%(asctime)-15s %(message)s'
        logging.basicConfig( filename=pjoin( self.meta_path, "all.log" ),
                level=logging.DEBUG, format=FORMAT )

        # Path accessors
    def metap( self, path ):
        """Retrieve path from the meta-store"""
        return pjoin( self.meta_path, path )

    def meta( self, path, mode = 'r' ):
        """Retrieve a file from the meta-store"""
        path = self.metap(path)
        if not pexists( dirname( path ) ): 
            os.makedirs( dirname( path ) )
        return open( path, mode )

    def outgoingp( self, path ):
        """Retrieve path from the meta-store"""
        return pjoin( self.outgoing_path, path )

    def outgoing( self, path, mode = 'r' ):
        """Retrieve a file from the meta-store"""
        path = self.outgoingp(path)
        if not pexists( dirname( path ) ): 
            os.makedirs( dirname( path ) )
        return open( path, mode )

    # Convenience functions
    def template( self, in_path, out_path = None ): 
        """Template in_path using the variables section"""
        if out_path is None:
            out_path = in_path
        # Replace the template variables
        buf = string.Template( open( in_path, "r").read()
                ).safe_substitute( self.variables )
        open( out_path, "w" ).write( buf )

    def cache( self, name, blob_or_path): 
        """Cache a file at path in the meta directory"""
        if isinstance( blob_or_path, git.Blob ):
            blob = blob_or_path
        else:
            blob = self.repo.tree()[ blob_or_path ]
        # For working tree files
        if blob.binsha == blob.NULL_BIN_SHA:
            self.copy( blob.abspath, self.metap( name ) )
        else:
            blob.stream_data( self.meta( name, "w" ) )
        # If this is a text file, replace the template variables
        ty = mimetypes.guess_type( blob.path )[0]
        if ty is not None and ty.split("/")[0] == "text":
            self.template( self.metap(name) )

    def ignores( self, base ):
        """Extract set of ignored files"""
        if self.conf.has_section( base ) and self.conf.has_option( base,
                "ignores" ):
            ignores = self.conf.get( base, "ignores" ).split(',')
            ignores = map( lambda fn: pjoin( base, fn.strip() ), ignores )
        else:
            ignores = []
        return set( ignores )

    def current_rev( self ):
        """Get the current revision from meta folder"""
        if( pexists( self.metap( self.REV_NAME ) ) ):
            return self.meta( self.REV_NAME ).read().strip()
        else:
            return None

    # Compilation
    def pandoc( self, src, target ):
        """Run pandoc on src to target. Uses conf to get theme"""

        if not pexists( dirname( target ) ): 
            os.makedirs( dirname( target ) )

        cmd = "pandoc --mathjax -s --template %s -o %s %s" % (
                self.metap("theme.html"), target, src )

        proc = sp.Popen( cmd.split() )
        if proc.wait() == 0:
            logging.info( "Compiled file %s", target)
        else:
            logging.info( "Error compiling file %s", target )

    def copy( self, infile, outfile ):
        """Copy file from A to B"""
        if not pexists( dirname( outfile ) ):
            os.makedirs( dirname( outfile ) )
        open( outfile, "w" ).write( open( infile, "r" ).read() )


    def compile( self, blob ):
        """Compile blob to outgoing"""
        self.cache( blob.path, blob )

        # Compile pandoc files
        if blob.path.endswith( PANDOC_EXTN ):
            path = self.outgoingp( blob.path[:-len(PANDOC_EXTN)] + ".html" )
            self.pandoc( self.metap(blob.path), path )
        else:
            # Copy the rest
            path = self.outgoingp( blob.path )
            self.copy( self.metap(blob.path), path )

    def delete( self, blob ):
        """Delete blob from outgoing"""

        # Handle extension changes
        if blob.path.endswith( PANDOC_EXTN ):
            path = blob.path[:-len(PANDOC_EXTN)] + ".html"
        else:
            path = blob.path
        path = self.outgoingp( path )
        if os.path.exists( path ):
            os.unlink( path )
            logging.info( "Deleted %s", path)
        else:
            logging.info( "Not found: %s", path)

    # Update handlers
    def changes( self, from_rev, to_rev = None ):
        """Get list of all files that need to be compiled at this level"""
        diffs = self.repo.commit( from_rev ).diff( to_rev )
        return ChangeSet.from_diffiter( from_rev, diffs )

    def apply( self, tree, cs ):
        """Recursively apply the changeset in this directory base"""
        base = tree.path

        if len(cs) == 0: 
            return
        ignores = self.ignores( base )

        # Apply updates to all files
        cs_ = cs.pop( base )
        logging.info( "Applying %d changes in %s", len(cs_), base )
        for blob in cs_.modifys.difference( ignores ):
            self.compile( blob )
        for blob in cs_.deletes.difference( ignores ):
            self.delete( blob )

        # Recurse
        for t in tree.trees:
            cs = self.apply( t, cs )

        # Update index
        self.build_index( tree )

        return cs

    def extract_meta( self, blob ):
        """Extract a timestamp from a post file"""
        self.cache( blob.path, blob )
        lines = self.meta( blob.path ).readlines()

        commits = self.repo.blame( "HEAD", blob.path )

        # First line is reserved for title
        # If title starts with a %, delete
        if blob.path.endswith( PANDOC_EXTN ):
            title = lines[0].strip()
            if title.startswith("%"):
                title = title[1:].strip()
        else:
            title = "`%s`" % blob.path

        # Get the date
        created = None
        fmts = ["%b %d %Y", "%B %d %Y", "%d %b %Y"]
        if len( lines ) >= 3 and lines[2].startswith("%"):
            try:
                created = get_date( fmts, lines[2][1:].strip() )
            except ValueError:
                created = None

        # Try using the title as a name (works for diary entries)
        if created is None:
            try:
                created = get_date( fmts, title )
            except ValueError:
                created = None

        # Give up and use the commit time
        if created is None:
            created = time.strptime( time.ctime(
                commits[0][0].committed_date ) )

        updated = time.strptime( time.ctime(
            commits[-1][0].committed_date ) )
        return title, created, updated

    def find(self, tree, x):
        """Workaround because x in tree doesn't work"""
        try:
            return tree[x]
        except KeyError:
            return None

    # Index generation
    def build_index(self, tree):
        """Build index for tree"""
        base = tree.path

        # TODO: Replace template variables
        if self.find( tree, "index.md" ) is not None or self.find( tree,
                "index.html" ) is not None:
            logging.info( "Keeping existing index for %s", base )
            return
        logging.info( "Building index for %s", base )

        # Create index of all files
        idx = []
        for blob in tree.blobs:
            title, created, updated = self.extract_meta( blob )

            if blob.path.endswith(PANDOC_EXTN):
                path = blob.path[:-len(PANDOC_EXTN)] + ".html"
            else:
                path = blob.path
            idx.append( (title, created, updated, path) )

        fd = self.meta( pjoin(base, "index.md"), "w" )
        fd.write( "%% %s\n\n"%(tree.name.capitalize()) )
        idx.sort( key=lambda i: i[1], reverse=True )
        for i in range(len(idx)):
            title, created, updated, path = idx[i]
            fd.write( " %d. [%s]($urlroot/%s) _(%s)_\n"%( i+1,
                title, path, time.strftime( "%d %b %Y", created) ) )
        fd.close()
        self.template( self.metap( pjoin(base, "index.md") ) )
        self.pandoc( self.metap( pjoin(base, "index.md") ), 
                self.outgoingp( pjoin(base, "index.html") ) ) 

        # If no existing index, build an index
        logging.info( "Updating index for %s", base )

    # Entry point
    def build(self, from_rev, to_rev, incremental = False):
        """Build the site to head_rev"""

        print "Building (incremental=%s)..."% str(incremental)
        logging.info( "Build initiated with incremental = %s",
                str(incremental) )

        if from_rev is None:
            from_rev = self.current_rev()
        if from_rev is None or not incremental:
            cs = ChangeSet.from_repo( self.repo )
        else:
            cs = self.changes( from_rev, to_rev ) 

        # Check if the theme has been modified
        theme = self.conf.get( "/", "theme" )
        if cs.exists( theme ):
            # Oh noes, theme has been changed recompile
            cs = ChangeSet.from_repo( self.repo )

        self.cache( "theme.html", theme )

        # Apply recursively from the root
        self.apply( self.repo.tree(), cs )

        save_rev = self.repo.commit().hexsha if to_rev == None else to_rev
        self.meta( self.REV_NAME, "w" ).write( save_rev )

def main( conf_path, from_rev, to_rev, incremental = False ):
    """Sitegen entry point"""

    gen = SiteGenerator( conf_path )
    gen.build( from_rev, to_rev, incremental )

if __name__ == "__main__":
    import argparse

    PARSER = argparse.ArgumentParser( description = "Static site generator" )
    PARSER.add_argument( "--conf", dest="conf", default="website.conf",
            help="Path to configuration file" ) 
    PARSER.add_argument( "-i", dest="incremental", action='store_true',
            default=False, help="Incrementally generate files" ) 
    PARSER.add_argument( "-f", dest="from_rev",
            default=None, help="Recompile from this rev. Needs -i" ) 
    PARSER.add_argument( "-t", dest="to_rev",
            default=None, help="Recompile to this rev, from current. Needs -i" ) 
    ARGS = PARSER.parse_args()

    main( ARGS.conf, ARGS.from_rev, ARGS.to_rev, ARGS.incremental )

