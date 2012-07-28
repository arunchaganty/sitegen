#!/usr/bin/env python2
"""
Convert a wordpress database to a set of markdown files
"""

import os
import time
import logging
import tempfile
import MySQLdb as DB
import subprocess as sp

PANDOC_EXTN = ".md"

def run_pandoc( src, target ):
    """Run pandoc on src to target. Uses conf to get theme"""
    cmd = "pandoc -f html -t markdown %s -o %s " % ( src, target)

    proc = sp.Popen( cmd.split() )
    if proc.wait() == 0:
        logging.info( "Converted file %s", target)
    else:
        logging.info( "Error converting file %s", target )

def get_posts( args, conn ):
    """Get all posts as a generator"""
    cur = conn.cursor()
    # TODO: Extract tag information as well
    cur.execute( "SELECT post_title, post_date, post_content FROM\
            %s_posts WHERE post_type='post' AND post_status='publish'\
            "%(args.prefix) )

    # Now generate new posts
    post = cur.fetchone()
    while post is not None:
        yield post
        post = cur.fetchone()

def write_markdown( post ):
    """Convert a post entry to markdown"""
    title, date, content = post
    temp = tempfile.NamedTemporaryFile()
    temp.write( content )
    temp.flush()

    target = filter( lambda c: c.isalnum() or c.isspace(),
            title).lower().replace(' ','-') + PANDOC_EXTN
    while( not target[0].isalnum() ):
        target = target[1:]
    run_pandoc( temp.name, target )
    temp.close()

    # Add header
    target_contents = open(target).read()
    target_contents = "%% %s\n%% \n%% %s\n" % (title, date.ctime()) +\
                        target_contents
    open(target,"w").write(target_contents)

def main( args ):
    """Entry point"""
    # Open 
    conn = DB.connect( args.host, args.user, args.passwd, args.db )
    logging.basicConfig( level=logging.INFO )

    posts = get_posts( args, conn )

    for post in posts:
        write_markdown( post )


if __name__ == "__main__":
    import argparse

    PARSER = argparse.ArgumentParser( 
            description = "Converter for wordpress blogs" )
    PARSER.add_argument( "-u", dest="user", help="Database username", required=True )
    PARSER.add_argument( "-p", dest="passwd", help="Database password", required=True )
    PARSER.add_argument( "--db", dest="db", help="Database name", required=True )
    PARSER.add_argument( "--host", dest="host", default="localhost",
            help="Database host" )
    PARSER.add_argument( "--prefix", dest="prefix", default="wp",
            help="Wordpress prefix" )

    ARGS = PARSER.parse_args()

    main( ARGS )

