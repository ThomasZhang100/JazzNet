'''
Preproccessing: 
Reading the wjazzd db into 3d datastructure:
array of vectors including pitch, duration, chord data for each note in each song
3d array/numpy array (songs, notes, notedata)

data structure saved to pickle file for use in training 
'''

import sqlite3
import numpy as np
from chordprocessing import chordString_2_vector

n_proc = 4

DUR_PER_BEAT = 24

con = sqlite3.connect("wjazzd.db")
cur = con.cursor() # cursor used object used to query 

num_songs = len(cur.execute('SELECT * FROM solo_info').fetchall())
#print(num_songs)


songdata = np.array(int)
uniquedurations = []

'''
cur.execute('SELECT pitch FROM melody')
pitches = cur.fetchall()
'''

maxPitch = 98.0
minPitch = 36.0 
pitchTop = maxPitch-minPitch
restPitch = pitchTop+1
    
'''
print(allchords)

{'6': 682, '7': 12222, '-7': 6762, '': 1376, '7alt': 164, 'j7': 3052, 'm7b5': 1117, '79b': 612,
'-': 810, '79#': 152, 'o7': 201, 'NC': 401, '-6': 394, 'o': 334, '79': 218, 'sus7': 371, '+7': 219,
    '7913': 105, '7911#': 131, 'sus79': 30, '69': 67, 'sus': 311, '-69': 49, '-79b': 1, '-j7': 34, 
    'j79': 34, 'j7911#': 174, '79b13b': 19, '+7911#': 2, '7913b': 8, '-79': 116, '79#13': 2, 
    '+79b': 1, '-7911': 105, '79b13': 7, 'j79#11#': 1, 'sus7913': 143, '6911#': 5, '+79': 5, 
    '+j7': 7, '+': 47, '+79#': 22, '79#11#': 8, 'j79#': 2, '-j7913': 8, '-j7911#': 8, 
    '-7913': 8, '7911': 1}
'''

#esclude non 4/4 indeces 

'''
cur.execute('SELECT signature, melid FROM solo_info')
signatures = cur.fetchall()
NCsongs=[]
for signature, melid in signatures:
    if signature!="4/4" and melid not in NCsongs:
        NCsongs.append(melid)
print(NCsongs)
'''




excludedSongs = [50, 66, 84, 147, 184, 185, 187, 188, 214, 215, 227, 228, 229, 246, 308, 322, 336, 337, 338, 339, 340, 403, 404, 405, 407, 411, 412, 431, 433, 434, 439]
print("num songs excluded:", len(excludedSongs))


def getSongNotes(melid, uniquedurs):
    cur.execute('SELECT eventid, bar, beat, onset, duration, beatdur, pitch FROM melody WHERE melid=? AND bar>0', (melid,))
    rows = cur.fetchall()
    first_two_beats = cur.execute('SELECT onset FROM beats WHERE melid=? AND bar>0 LIMIT 2', (melid,)).fetchall()
    approx_beat_dur = first_two_beats[1][0]-first_two_beats[0][0]
    songnotes = []
    end_measure_offset=0
    end_bar=1
    end_beat=1
    for row in rows:
        note = list(row)
        bar, note_beat, onset, duration, beatdur, pitch = note[1], note[2], note[3], note[4], note[5], note[6]
        cur.execute('SELECT onset, chord FROM beats WHERE melid=? AND bar=? AND beat=?', (melid, bar, note_beat))

        beat_onset, chord = cur.fetchone()
        note_end = onset + duration

        #calculating the offset of the beginning of the note with respect to its beat and measure
        onset = beat_onset if beat_onset>onset else onset
        note_beg_offset = round((onset-beat_onset)/beatdur*DUR_PER_BEAT)

        #just in case we round up to the next beat 
        if note_beg_offset>(onset-beat_onset)/beatdur*DUR_PER_BEAT and note_beg_offset%DUR_PER_BEAT==0:
            #print("rounded beginning up to next beat")
            note_beg_offset=0
            note_beat+=1
            if note_beat>4:
                note_beat=1
                bar+=1
            chord = cur.execute('SELECT chord FROM beats WHERE melid=? AND bar=? AND beat=?', (melid, bar, note_beat)).fetchone()[0]

        measure_offset = (note_beat-1)*DUR_PER_BEAT+note_beg_offset

        #if there is a gap between this note and the previous one, add a rest note to array
        #if rest_duration smaller than certain number, add rest duration to previous note
        if not (measure_offset==end_measure_offset and bar == end_bar):
            #if bar<6:
                #print("bar:",bar,"end_bar:",end_bar,"measure_offset:",measure_offset,"end_measure_offset:", end_measure_offset)
            rest_duration = DUR_PER_BEAT * 4 * (bar-end_bar) - end_measure_offset + measure_offset
            if rest_duration<3 and len(songnotes)!=0:
                songnotes[-1][1]+=rest_duration
            else:
                try:
                    rest_chord = cur.execute('SELECT chord FROM beats WHERE melid=? AND bar=? AND beat=?', (melid, end_bar, end_beat)).fetchone()[0]
                except:
                    print("end_bar:", end_bar, "end_beat:", end_beat)
                rest_fournotes, rest_chordtype = chordString_2_vector(rest_chord)
                songnotes.append([restPitch,rest_duration,end_measure_offset]+rest_fournotes+[rest_chordtype])
                if rest_duration not in uniquedurs:
                    uniquedurs.append(rest_duration)
                #print("rest duration:", rest_duration, "chord:", rest_chord, "measure_offset:", end_measure_offset)
            

        fournotes, chordtype = chordString_2_vector(chord)


        #check for notes extending past one beat
        num_beats_apart=0
        end_beat_onset=beat_onset
        end_beat = note_beat
        end_bar = bar
        while True:
            end_beat+=1
            if end_beat > 4:
                end_beat=1
                end_bar+=1
            cur.execute('SELECT onset FROM beats WHERE melid=? AND bar=? AND beat=?', (melid, end_bar, end_beat))
            try:
                next_beat_onset = cur.fetchone()[0]
            except:
                next_beat_onset = end_beat_onset + approx_beat_dur
            if note_end<next_beat_onset:
                break
            else:
                num_beats_apart+=1
                end_beat_onset=next_beat_onset
        
        #calculating the offset of the note end with respect to its beat
        note_end_offset_raw = (note_end-end_beat_onset)/(next_beat_onset-end_beat_onset)
        note_end_offset = round(note_end_offset_raw*DUR_PER_BEAT)
        #just in case we round up to the next beat 
        if note_end_offset>note_end_offset_raw*DUR_PER_BEAT and note_end_offset%DUR_PER_BEAT==0:
            #print("rounded end up to next beat")
            note_end_offset=0
            num_beats_apart+=1
        else:
            #correcting the position of the end of the note to calculate the measure offset of the end of the note
            end_beat-=1
            if end_beat < 1:
                end_beat=4
                end_bar-=1

        end_measure_offset = (end_beat-1)*DUR_PER_BEAT+note_end_offset

        #calculating the rounded duration of the note (quantized by DUR_PER_BEAT)
        rounded_duration = DUR_PER_BEAT * num_beats_apart - note_beg_offset + note_end_offset

        if rounded_duration not in uniquedurs:
            uniquedurs.append(rounded_duration)

        #if bar<6:
            #print([int(pitch-minPitch),rounded_duration,measure_offset]+fournotes+[chordtype])

        #print('melid:',i,'bar:',bar,'beat:',note_beat)
        #print("duration:",rounded_duration,"pitch:",int(pitch-minPitch),"chord:",chord,"measure_offset:", measure_offset)
        songnotes.append([pitch-minPitch,rounded_duration,measure_offset]+fournotes+[chordtype])
        #add note to array 
    
    return np.array(songnotes).astype(int)

for i in range(1,num_songs+1):
    if i in excludedSongs:
        continue

    print("song:",i)
    songNotes = getSongNotes(i, uniquedurations)
    np.append(songdata,songNotes)


durationslist = sorted(uniquedurations)
print("unique durations:", durationslist)

con.close()

'''
bar: 1 end_bar: 1 measure_offset: 3 end_measure_offset: 0
[22, 15, 3, 10, 2, 5, 9, 3]
bar: 1 end_bar: 1 measure_offset: 27 end_measure_offset: 18
[22, 39, 27, 10, 2, 5, 9, 3]
bar: 3 end_bar: 1 measure_offset: 53 end_measure_offset: 66
[14, 14, 53, 7, 10, 2, 5, 2]
bar: 3 end_bar: 3 measure_offset: 76 end_measure_offset: 67
[21, 12, 76, 7, 10, 2, 5, 2]
bar: 3 end_bar: 3 measure_offset: 90 end_measure_offset: 88
[24, 9, 90, 7, 10, 2, 5, 2]
bar: 4 end_bar: 4 measure_offset: 5 end_measure_offset: 3
[22, 10, 5, 0, 3, 7, 10, 2]
bar: 4 end_bar: 4 measure_offset: 18 end_measure_offset: 15
[19, 8, 18, 0, 3, 7, 10, 2]
bar: 4 end_bar: 4 measure_offset: 40 end_measure_offset: 26
[22, 7, 40, 0, 3, 7, 10, 2]
bar: 4 end_bar: 4 measure_offset: 49 end_measure_offset: 47
[25, 23, 49, 5, 9, 0, 3, 0]
bar: 4 end_bar: 4 measure_offset: 73 end_measure_offset: 72
[24, 13, 73, 5, 9, 0, 3, 0]
bar: 4 end_bar: 4 measure_offset: 87 end_measure_offset: 86
[22, 8, 87, 5, 9, 0, 3, 0]
bar: 5 end_bar: 4 measure_offset: 0 end_measure_offset: 95
[24, 33, 0, 5, 8, 0, 3, 2]
bar: 5 end_bar: 5 measure_offset: 36 end_measure_offset: 33
rounded end up to next beat
[22, 12, 36, 5, 8, 0, 3, 2]
bar: 5 end_bar: 5 measure_offset: 50 end_measure_offset: 48
[20, 11, 50, 10, 2, 5, 8, 0]
bar: 5 end_bar: 5 measure_offset: 63 end_measure_offset: 61
[24, 10, 63, 10, 2, 5, 8, 0]
bar: 5 end_bar: 5 measure_offset: 75 end_measure_offset: 73
[23, 9, 75, 10, 2, 5, 8, 0]
bar: 5 end_bar: 5 measure_offset: 87 end_measure_offset: 84
rounded end up to next beat
[21, 9, 87, 10, 2, 5, 8, 0]

'''

