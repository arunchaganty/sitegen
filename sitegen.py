#!/usr/bin/env python2
"""
sitegen.py is a static site generator for arun.chagantys.org
"""

import os
import shutil
import git
import ConfigParser as CP
import itertools as it
import logging

PANDOC_EXTN = ".pdc"

def compile_index( conf, tree, target ):
    """Compile an index of articles from a git tree""" 
    pass

def save_file( conf, blob, target ):
    """Save a blob as in to target""" 
    fstream = open( target, "w" )
    blob.stream_data( fstream )
    fstream.close()

def compile_file( conf, blob, target ):
    """Compile an article from a git blob""" 
    logging.info( "Compiling file %s to target %s"%( blob.path, target ) )

def get_current_rev( conf ):
    """Try to the current revision from the meta files"""
    meta = conf.get( "paths", "meta" )
    rev = os.path.join( meta, "current_rev" )
    if os.path.exists(rev):
        rev = open( rev ).read().strip()
        return rev
    else:
        return None

def get_changelist( conf, repo, rev=None ):
    """Get list of files that have changed since the last update""" 
    #TODO: Handle ignore lists
    if rev:
        # if a last update exists, then find diffs since the last rev
        diffs = repo.index.diff( rev )
        # Add all the b_blobs of this list
        updates = it.ifilter( None, map( lambda d: d.b_blob, diffs ) ) 
        deletes = map( lambda d: d.a_blob, it.chain(
            diffs.iter_change_type('D'), diffs.iter_change_type('R') ) )
    # Otherwise, just make everything in the gitrepo
    else:
        updates = filter(lambda x: isinstance( x, git.Blob),
                repo.tree().traverse())
        # TODO: Compare with existing files, and prune.
        deletes = []
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
            logging.info( "Deleted %s"%(path))

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

    # Get updates
    updates, deletes = get_changelist( conf, repo, get_current_rev( conf ) )
    logging.info( "Updating %d, Deleting %d"%(len(updates), len(deletes)) )
    update_files( conf, updates )
    delete_files( conf, deletes )

    # Create indexes for all the sections
    # TODO:
    # sections = map( str.strip, conf.get("root","sections").split(',') )

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser( description = "Static site generator" )
    parser.add_argument( "--conf", dest="conf", default="website.conf",
            help="Path to configuration file" ) 
    args = parser.parse_args()

    main( args.conf )

