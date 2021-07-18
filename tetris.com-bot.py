# Tetris.com

import pyautogui
from PIL import Image
import numpy as np
import time
import random
import keyboard
import math


# Weights for the criteria
HEIGHT_SIMPLE = -3 # Unit of height (overall)
HEIGHT_COEFF = 1.4 # For progressive weght of height i**coeff for each next row
WIDTH_COEFF = 3 # For regressive count of width on certain height (more for less effect)

HEIGHT_DIFFERENCE = -5 # Each step between neighbouring rows
HOLE = -500
OVERHEAD = -10 # Cells above the hole

LINE_1 = 0
LINE_2 = 0
LINE_3 = 1000
LINE_4 = 10000
UNWANTED_LINE = -1000

DIVERSITY = 50 # Has a spot for all kinds of tetraminos
EXTRA_WELLS = -300 # More than one well (hole >2 deep)

HAS_LAST_COLUMN = -2000
PENULTIMATE_COLUMN_PROBLEM = -1000

mode = 2 # control the behaviour
# 0 fixing the holes
# 1 ready for a stick
# 2 building a monolith with a well

show_scores = False


# return pixel's brightness
def brightness(px):
    return int((px[0]+px[1]+px[2])/3)

# Is a pixel of that color that we use to find the border?
def is_border_color(px):
    if px[0]==36 and px[1]==35 and px[2]==35:
        return True
    return False

# get the inner top border
def get_top_border(im):
    px = im.load()
    found_borders = []
    for i in range(0, im.size[0], im.size[0]//30):
        for j in range(2, im.size[1]):
            if not is_border_color(px[i,j]) \
               and is_border_color(px[i,j-1]) \
               and is_border_color(px[i,j-2]):
                if len(found_borders)>0 and abs(j-found_borders[-1])<2:
                    found_borders.append(found_borders[-1])
                else:    
                    found_borders.append(j)
                break
    #print (found_borders)
    for found_border in found_borders:
        if found_borders.count(found_border) > len(found_borders)//2:
            return found_border

# Get four borders
def get_borders(im):
    top = get_top_border(im)
    left = get_top_border(im.transpose(Image.ROTATE_270))
    bottom = im.size[1] - get_top_border(im.transpose(Image.ROTATE_180))
    right = im.size[0] - get_top_border(im.transpose(Image.ROTATE_90))
    return (left, top, right, bottom)

# Read square, return 1 (has block), 0 (empty)
def read_square(im):
    treshold = 5
    total = 0
    px = im.load()
    for i in range(im.size[0]):
        for j in range(im.size[1]):
            total += brightness(px[i,j])
    if total // ( im.size[0] *  im.size[1] ) > treshold:
        return 1
    return 0
            
            

# Read whole the image return NP array
def read_field(im):
    field = np.zeros((10,20), dtype=int)
    delta = 5
    for i in range(10):
        for j in range(20):
            x = int(im.size[0]*i/10+im.size[0]/20)
            y = int(im.size[1]*j/20+im.size[1]/40)
            cell_block = im.crop(((x-delta, y-delta, x+delta, y+delta)))
            field[i,j] = read_square(cell_block)
    return field


# if the line N of the field all empty
def is_empty_line(field, n):
    for i in range(10):
        if field [i,n] != 0:
            return False
    return True

# Add empty column to the right of the piece
def add_empty_line_from_right(piece_input):
    piece = np.copy(piece_input)
    dim1 = len(piece)
    dim2 = len(piece[0])
    to_append = np.zeros((dim1, 1), dtype=int)
    piece = np.append(piece, to_append, 1)
    return piece

# Make a piece a square array
def make_it_square(piece_input):
    piece = np.copy(piece_input)
    while len(piece)!=len(piece[0]):
        piece = add_empty_line_from_right(piece)
    return piece

# Get a piece from the read field (from 2 lines before the empty line)    
def get_piece(field):
    for j in range(1,20):
        if  is_empty_line(field, j) and not is_empty_line(field, j-1):
            top = j-2
            break
    piece_list = []
    left = -1
    leftover_flag = False
    for i in range(10):

        # This is a messy bit. This is a protectin for cases when some leftover lines mistakenly identified as a piece. And worng decisions are made.
        if leftover_flag and i <9 and \
           (field[i+1, top] != 0 or field[i+1, top+1] != 0) and \
           (field[i, top] == 0 and field[i, top+1] == 0):
            print ("Leftover lines")
            return False
        if i > 0 and \
           (field[i-1, top] != 0 or field[i-1, top+1] != 0) and \
           (field[i, top] == 0 and field[i, top+1] == 0):
            leftover_flag = True
        # End of messy bit
        
        if field[i, top] != 0 or field[i, top+1] != 0:
            if left == -1:
                left = i
            piece_list.append(field[i, top])
            piece_list.append(field[i, top+1])

    if piece_list.count(1)!=4:
        return False
    
    piece = np.asarray(piece_list, dtype = int) 
    piece = np.reshape(piece, (len(piece_list)//2, 2))
    piece = make_it_square(piece)
    return piece, left

# Return array with 4 versions of a piece (rotations) 
def get_rotations(piece):
    rotations = []
    for i in [0,1,2,3]:
        rotations.append(np.rot90(piece, k=i))
    return rotations

# Return only bottom part of the field (minus  the piece)        
def get_floor(field):
    ''' gett the botttom "landscape" + 4 empty lines '''
    for j in range(19,0, -1):
        if  is_empty_line(field, j):
            break
    return np.append(np.zeros((10,4), dtype=int), field[0:10, j+1:20], axis=1)

def is_legit_position(piece, position):
    ''' See if the piece seps out of the field'''
    if position < 0:
        for i in range (abs(position)):
            if max(piece[i]) != 0:
                return False
    if position + len (piece) > 10:
        for i in range( position + len (piece)-10 ):
            if max(piece[-i-1]) != 0:
                return False
    return True
            
def get_new_floor(floor, orig_piece, orig_position):
    ''' Resulting new "landscape" when piece is dropped '''
    #print (floor)
    #print ("1. Original:\n", orig_piece, orig_position)
    piece = orig_piece.copy()
    position = orig_position

    # trim sides
    if position < 0:
        for i in range(abs(position)):
            piece = np.delete(piece, 0, 0)
        position = 0
    if position + len (piece) > 10:
        for i in range( position + len (piece)-10 ):
            piece = np.delete(piece, -1, 0)
    #print ("2: Trimmed out of glass\n", piece, position)

    # Exteend to 0
    if position > 0:
        piece = np.append(\
            np.zeros ( (position, len(piece[0])), dtype=int ),
            piece,
            0, )        
    #print ("3. Extented to the top:\n", piece, position)
    if orig_position +len (orig_piece) < 10:
        piece = np.append(\
            piece,
            np.zeros ( (10-orig_position-len(orig_piece), len(piece[0])), dtype=int ),
            0, )        
    #print ("4. Extented to the bottom:\n", piece, position)

    while is_empty_line(piece, len(piece[0])-1):
        piece = piece [0:10, 0:len(piece[0])-1]
    #print ("5. Trim from the right:\n", piece, position)

    
    # deep it in, see when itt starts ovelapping
    for depth in range(0, len(floor[0])-len(piece[0])+1):
        # extent it from the left and right
        temp_piece = piece.copy()
        temp_piece = np.append(\
            np.zeros ( (10, depth), dtype=int ),
            temp_piece,
            1, )        
        temp_piece = np.append(\
            temp_piece,
            np.zeros ( (10, len(floor[0])-depth-len(piece[0])), dtype=int ),
            1, )
        #print ("6. Piece ready to merge:\n", temp_piece)
        merged = np.add(floor, temp_piece)
        #print ("7. Floor and piece:\n", merged)
        if np.amax(merged)==2:
            return last_valid
        last_valid = merged.copy()
    return last_valid



def collapse_floor(floor):
    cell_counts = np.sum(floor, axis=0)
    new_floor = floor.copy()
    lines = 0
    for i in range(len(cell_counts))[::-1]:
        if cell_counts[i]==10:
            lines +=1
            new_floor = np.delete(new_floor, i, 1)
    return (new_floor, lines)
            


def get_height(floor):
    cell_counts = np.sum(floor, axis=0)
    height = np.count_nonzero(cell_counts)
    return height

def get_height_adv(floor):
    height_list = []
    cell_counts = np.sum(floor, axis=0)
    return cell_counts
##    for i in range(len(floor[0]))[::-1]:
##        if cell_counts[i] > 0:
##            height_list.append(1)
##        else:
##            height_list.append(0)
##    return height_list


def get_holes(floor):
    holes = 0
    overhead = 0
    for i in range(10):
        found_cell = False
        over_in_row = 0
        for j in range(len(floor[0])):
            if floor[i,j]==1:
                found_cell = True
                over_in_row+=1
            if found_cell and floor[i,j]==0:
                holes += 1
                overhead += over_in_row
    return holes, overhead

def get_hgt_differences(floor):
    h_diffs = 0
    heights = np.sum(floor, axis=1)
    for i in range(1, 10):
        h_diffs += abs(heights[i]-heights[i-1])
    return h_diffs

def get_diversity(floor):
    a, b, c = False, False, False
    heights = np.sum(floor, axis=1)
    for i in range(1, 10):
        if heights[i]-heights[i-1] == 0:
            a = True
        if heights[i]-heights[i-1] == 1:
            b = True
        if heights[i]-heights[i-1] == -1:
            c = True
    return a and b and c
            


def last_column(floor):
    if np.sum(floor[9]) > 0:
        return True
    return False

def count_wells(floor):
    wells = 0
    heights = np.sum(floor, axis=1)
    if heights[1]-heights[0]>2:
        wells +=1
    if mode !=2 and heights[8]-heights[9]>2:
        wells +=1
    for i in range(1, 8):
        if heights[i-1]-heights[i]>2 and heights[i+1]-heights[i]>2:
            wells +=1
    return wells
            
    

def get_score(orig_floor):

    score = 0
    sc_lines = 0
    sc_holes = 0
    sc_overhead = 0
    sc_height = 0
    sc_diff = 0
    sc_diverse = 0
    sc_wells = 0
    
    # Check for full lines
    floor, lines = collapse_floor(orig_floor)

    # Completed lines
    if mode != 2:
        if lines == 1:
            sc_lines = LINE_1
        if lines == 2:
            sc_lines =sc_lines = LINE_2
        if lines == 3:
            sc_lines = LINE_3
        if lines == 4:
            sc_lines = LINE_4
    elif lines>0:
        score += UNWANTED_LINE
    score += sc_lines    

    # Holes (less is beter)
    holes, overhead = get_holes(floor)
    sc_holes = holes * HOLE
    sc_overhead = overhead * OVERHEAD
    score += sc_holes
    score += sc_overhead
    
    # Height (less is beter)
    #score += get_height(floor) * HEIGHT_SIMPLE

    # Height advanced (progressive weight)
    height_list = get_height_adv(floor)
    #print (height_list)
    for i in range(len(floor[0])):
        if height_list[-i-1]>0:
            #print (i, height_list[-i-1], HEIGHT_SIMPLE*HEIGHT_COEFF**i, math.log(height_list[-i-1],WIDTH_COEFF)+1)
            height_score = height_list[-i-1] * HEIGHT_SIMPLE * (HEIGHT_COEFF**i) * (math.log(height_list[-i-1],WIDTH_COEFF)+1)
            if mode ==2:
                sc_height += height_score/2
            else:
                sc_height += height_score
    score += sc_height
    
    # Height differences
    sc_diff = get_hgt_differences(floor) * HEIGHT_DIFFERENCE
    score += sc_diff
    
    if get_diversity(floor):
        sc_diverse = DIVERSITY
        score += sc_diverse
        
    wells = count_wells(floor)
    if wells >0:
        sc_wells = wells * EXTRA_WELLS
        score += sc_wells
         
##    # Has stuff in last column (only for holeless situation)
    if mode == 2:
        if last_column(floor):
            score += HAS_LAST_COLUMN
        heights = np.sum(floor, axis=1)
        if heights[7]-heights[8] > 2:
            score += PENULTIMATE_COLUMN_PROBLEM

    if show_scores:
        print ("Lines:", sc_lines, "Holes:", sc_holes, "Overhead", sc_overhead, "Height:", sc_height)
        print ("Diff:", sc_diff, "Divers:", sc_diverse, "Wells", sc_wells)
            
    # Add dither
    score -= random.random()
    return score

def set_mode(floor):
    global mode
    
    holes, _ = get_holes(floor)
    if holes > 0:
        mode = 0 # fix a hole
        return
    heights = np.sum(floor, axis=1).tolist()
    if heights.count(0) == 1:
        heights.remove(0)
        if min(heights)>3:
            mode = 1 # ready for a stick
            return
    mode = 2 # building a thing
            
        
        

def do_permutations(piece, floor):
    rotations = get_rotations(piece)
    best_posiion = -1000000
    best_rotation = -1000000
    best_score = -1000000
    for position in range (-2, 9): # position of a piece
        for rotation in range (4): # rotation option off a piece
            rotated_piece = rotations[rotation]
            if is_legit_position(rotated_piece, position):
                
                new_floor = get_new_floor(floor, rotated_piece, position)
                score = get_score(new_floor)
                if show_scores:
                    print (new_floor)
                    print ("Pos:", position, "Rot:", rotation, "Score:", score)
                    print("-"*40)

                if score > best_score:
                    best_score = score
                    best_posiion = position
                    best_rotation = rotation
    print ("Best pos:", best_posiion, "Best rot:", best_rotation, "Best score:", best_score)
    return (best_posiion, best_rotation)

def do_the_move(start_x, best_posiion, best_rotation):
    
    def press(button):
        delay = 0.02
        if True: #need_to_click:
            #pyautogui.press(button)
            keyboard.send(button)
            time.sleep(delay)
        else:
            print (button)
    
    for i in range(best_rotation):
        press("up")
    if start_x < best_posiion:
        for i in range(best_posiion-start_x):
            press("right")
    if start_x > best_posiion:
        for i in range(start_x-best_posiion):
            press("left")

    press("space")

    

def main(im=""):
    fail_count = 0
    
    if im=="":
        need_to_click = True
        im = pyautogui.screenshot()

    else:
        need_to_click = False
        im = Image.open(im)
        
    try:
        borders = get_borders(im)
    except:
        print("Can't find the game")
        return

    while True:
        im = pyautogui.screenshot()
        #im.save("screenshots/"+str(time.time())+".png")
        cropped = im.crop(borders)
        field = read_field(cropped)
        #print (field)
        
        try:

            
            piece, start_x = get_piece(field)
            #print (start_x)    

            floor = get_floor(field)
            set_mode(floor)
            print (mode)
                        
            best_posiion, best_rotation = do_permutations(piece, floor)
            

            do_the_move(start_x, best_posiion, best_rotation)
            time.sleep(0.05)
            fail_count = 0
            
        except:
            fail_count += 1
            print("Skipping frame")
            if fail_count ==10:
                print("Game appears to be over")
                return
    print ("huh")

##        

##
##show_scores = True
##filename = "6.png"
##print (filename)
##im = Image.open(filename)
##borders = get_borders(im)
##print (borders)
##
##cropped = im.crop(borders)
##field = read_field(cropped)
##print (field)
##
##piece, start_x = get_piece(field)
####print (piece)    
####print (start_x)    
##
##rotations = get_rotations(piece)
###print (rotations)
##
##floor = get_floor(field)
###print (floor)
##
##
##best_posiion, best_rotation = do_permutations(piece, floor)
##print ("Best pos:", best_posiion, "Best rot:", best_rotation)
##
##get_score(floor)
##
##
##    do_the_move(start_x, best_posiion, best_rotation)
 
keyboard.add_hotkey('f10', main)
keyboard.wait('esc') 
