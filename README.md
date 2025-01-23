# Preservica-Deduplication
Process to run on exported collections in preservica to sort through duplicated collections and match correct PreservicaRef's found in Gamera

## deduplicate.sh
Bash script that takes in the exported.csv structure and pulls the SourceIDs from the inital csv. Then runs a drush command that pulls the rels-ext of each sourceID and stores the preservica Ref from the file. Both SourceID and preservicaRef gets stored in a new .csv file to be read by accessAPI.py

## accessAPI.py
takes in a .csv file with the first column being the sourceID (pitt:##########) and the second column being the subsequent preservica ref pulled from Gamera

using the SourceID and preservica Ref the following pseudocode is implemented:

            Find islandora_PIDs with an RELS-EXT islandora:preservicaRef
            Foreach islandora_PID
            Search Preservica's sourceID for the islandora_PID value
            Foreach Preservica RefId
                If the Preservica RefId has a root folder which is not "IslandoraIngests"
                If no RefId is flagged as authoritative
                    Flag this RefId as authoritative
                Else
                    Raise an error (mulitple are authoritative)
                    Move to the next islandora_PID
                EndIf
                EndIf
            EndForeach
            If No RefIf is flagged as authoritative
                Flag the last seen RefId as authoritative
            EndIf
            Foreach Preservica RefId
                If the RefId is flagged as authoritative
                If the islandora:preservicaRef differs
                    Update the islandora:preservicaRef in the RELS-EXT
                EndIf
                Else
                Mark the Preservica RefId to be moved to the ZZZ_DELETE folder
                EndIf
            EndForeach
            EndForeach

    
once the code executes the remaining file - update.csv will be used to run the move_to_trash function or the update_preservica_ref function depending on the key.

      

