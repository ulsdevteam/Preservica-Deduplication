#!/bin/bash

# 
# 


# Where is the ingest monitor message file downloaded from Preservica?
MESSAGEFILE=$1
if [ "$MESSAGEFILE" == "" ]
then
  >&2 echo "USAGE: $0 <filename>"
  exit 1
fi

# Where can we setup a temporary working directory?
TMPDIR=`mktemp -d`
# Have we seen any errors which require operator intervention?
ERRORFLAG=

# extract the first column (islandora PID) from each row
# Use a python script to extract the fifth (islandora identifier) and sixth (preservica identifier) columns from the CSV
cat <<'EOF'> $TMPDIR/extract-identifiers.py
import sys
import csv
with open(sys.argv[1], 'r') as csvfile:
  linereader = csv.reader(csvfile)
  for line in linereader:
    if line[0].startswith('pitt:'):
      print(line[0])
EOF
python $TMPDIR/extract-identifiers.py $MESSAGEFILE > $TMPDIR/islandora_PIDS.pipe


echo "python script finished successfully"

# extract the rels-ext for each pid
mkdir $TMPDIR/rels-ext
drush -qy --root=/var/www/html/drupal7/ --user=$USER --uri=http://gamera.library.pitt.edu islandora_datastream_crud_fetch_datastreams --pid_file=$TMPDIR/islandora_PIDS.pipe --dsid=RELS-EXT --datastreams_directory=$TMPDIR/rels-ext --filename_separator=^
if [[ $? -ne 0 ]]
then
  >&2 echo "CRUD fetch returned an error"
  ERRORFLAG=1
fi

echo "extracted all the rels-exts"

# Iterate across each PID
while read -r line
do
  # echo "line is $line"
  rels_ext_file=$TMPDIR/rels-ext/`echo $line`^RELS-EXT.rdf
  PREF=`echo $line`
  echo "PREF: $PREF"
  # Transform the RELS-EXT with our XSLT, adding in the new presericaExportDate
  # xsltproc --stringparam pref "$PREF" -o $i $TMPDIR/update-preservica-ingest.xsl $i
  # extract the ref
  # preservicaRef=$(xmllint --xpath "string(//rdf:Description/islandora:preservicaRef)" --noout --namespace-islandora="http://islandora.ca/ontology/relsext#" $rels_ext_file)
  preservicaRef=$(xmllint --xpath "string(//*[local-name()='preservicaRef' and namespace-uri()='http://islandora.ca/ontology/relsext#'])" $rels_ext_file)  
  echo "preservica ref from islandora: $preservicaRef"

  echo "$line,$preservicaRef" >> deduplicated.csv
done < $TMPDIR/islandora_PIDS.pipe


# Only delete the working directory if there were no errors
if [[ "$ERRORFLAG" = "" ]]
then
  rm -rf $TMPDIR
else
  >&2 echo "Examine $TMPDIR for errors"
  exit 2
fi