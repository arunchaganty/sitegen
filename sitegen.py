#!/usr/bin/env python2
"""
sitegen.py is a static site generator for arun.chagantys.org
"""

import os
import git
import logging
import tempfile
import subprocess as sp
import ConfigParser as CP
import itertools as it

PANDOC_EXTN = ".md"

# def compile_index( conf, tree, target ):
#     """Compile an index of articles from a git tree""" 
#     pass

def replace_constants( conf, target ):
    """Replace any of the predefined constants in files"""
    urlroot = conf.get( "paths", "urlroot" )
    # Call sed (it's probably more efficient)
    cmd = 'sed -i -e s#@ROOT@#%s#g %s'%(urlroot, target)
    p = sp.Popen( cmd.split() )
    p.wait()

def save_theme( conf, repo ):
    """Save the theme file from the git repo to a usable location"""
    theme = conf.get( "paths", "theme" )
    meta = conf.get( "paths", "meta" )
    blob = repo.tree()[ theme ]
    # Save to meta folder
    path = os.path.join(meta, "theme.html")
    blob.stream_data( open( path, "w") )
    replace_constants( conf, path )
    return path

def save_file( conf, blob, target ):
    """Save a blob as in to target""" 
    fstream = open( target, "w" )
    blob.stream_data( fstream )
    fstream.close()
    replace_constants( conf, target )
    # Replace all occurances of @ROOT@ with
    logging.info( "Copied over %s", target )

def compile_file( conf, blob, target ):
    """Compile an article from a git blob""" 
    meta = conf.get( "paths", "meta" )
    theme_path = os.path.join( meta, "theme.html" )
    
    path = os.path.join( meta, "_compile.md" )
    f = open( path, "w+b" )
    blob.stream_data( f )
    f.close()
    replace_constants( conf, path )
    # Save theme file to 
    cmd = "pandoc -S -s --template %s -o %s %s" % (
            theme_path, target, path )
    proc = sp.Popen( cmd.split() )
    if proc.wait() == 0:
        logging.info( "Compiled file %s to target %s", blob.path, target)
    else:
        logging.info( "Error compiling file %s to target %s", blob.path,
                target )

def get_current_rev( conf ):
    """Try to the current revision from the meta files"""
    meta = conf.get( "paths", "meta" )
    rev = os.path.join( meta, "current_rev" )
    if os.path.exists(rev):
        rev = open( rev ).read().strip()
        return rev
    else:
        return None

def save_current_rev( conf, repo ):
    """Try to the current revision from the meta files"""
    meta = conf.get( "paths", "meta" )
    rev = repo.commit().hexsha
    open( os.path.join( meta, "current_rev" ), "w" ).write( rev )

def get_changelist( conf, repo, rev=None ):
    """Get list of files that have changed since the last update""" 
    ignores = conf.get( "paths", "ignores" )
    if rev:
        # if a last update exists, then find diffs since the last rev
        diffs = repo.index.diff( rev )
        # Add all the b_blobs of this list
        updates = list( it.ifilter( None, map( lambda d: d.b_blob, diffs ) )  )
        deletes = map( lambda d: d.a_blob, it.chain(
            diffs.iter_change_type('D'), diffs.iter_change_type('R') ) )
    # Otherwise, just make everything in the gitrepo
    else:
        updates = filter(lambda x: isinstance( x, git.Blob),
                repo.tree().traverse())
        # TODO: Compare with existing files, and prune.
        deletes = []
    # Filter updates and deletes from the ignores list
    updates = filter( lambda b: b.name not in ignores, updates )
    deletes = filter( lambda b: b.name not in ignores, deletes )
    return updates, deletes

def update_files( conf, updates ):
    """Update all files in update in outgoing"""
    outgoing = conf.get( "paths", "outgoing" )
    # Compile all the files
    for blob in updates:
        path = os.path.join( outgoing, blob.path )
        if not os.path.exists( os.path.dirname( path ) ): 
            os.makedirs( os.path.dirname( path ) )
        if path.endswith( PANDOC_EXTN ):
            path = path[:-len(PANDOC_EXTN)] + ".html"
            compile_file( conf, blob, path )
        else:
            save_file( conf, blob, path)

def delete_files( conf, deletes ):
    """Delete all files in deletes from the outgoing"""
    outgoing = conf.get( "paths", "outgoing" )
    # Delete all said files from the target
    for blob in deletes:
        if blob.name.endswith( PANDOC_EXTN ):
            path = blob.name[:-len(PANDOC_EXTN)] + ".html"
        else:
            path = blob.path
        path = os.path.join( outgoing, path )
        if os.path.exists( path ):
            os.unlink( path )
            logging.info( "Deleted %s", path)

def main( conf_path ):
    """Sitegen entry point"""
    conf = CP.ConfigParser()
    conf.read( conf_path )
    incoming = conf.get( "paths", "incoming" )
    outgoing = conf.get( "paths", "outgoing" )
    meta = conf.get( "paths", "meta" )

    if not os.path.exists( meta ):
        os.mkdir( meta )
    # Configure the logger 
    logging.basicConfig( filename=os.path.join( meta, "all.log" ),
            level=logging.DEBUG )

    # Check the repo
    repo = git.Repo( incoming )

    # Save the theme
    save_theme( conf, repo )

    # Get updates
    updates, deletes = get_changelist( conf, repo, get_current_rev( conf ) )
    logging.info( "Updating %d, Deleting %d", len(updates), len(deletes) )
    update_files( conf, updates )
    delete_files( conf, deletes )

    # Create indexes for all the sections
    # TODO:
    # sections = map( str.strip, conf.get("root","sections").split(',') )

    # Save the current revision to the meta file
    #save_current_rev(conf, repo)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser( description = "Static site generator" )
    parser.add_argument( "--conf", dest="conf", default="website.conf",
            help="Path to configuration file" ) 
    args = parser.parse_args()

    main( args.conf )

