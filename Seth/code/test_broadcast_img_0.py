from pathlib import Path
import os
import itertools
from copy import deepcopy
import warnings
import json
import sys

import cv2
import numpy as np

import load_above
from part2 import get_projection_matrix, test_transition_matrix, get_transition_matrix, convert_vector
from part2 import main as part2main


def use_pairing(pairings):

    left_pixels = []
    right_pixels = []
    for pair in pairings:
        left, right = pair
        if left in left_pixels or right in right_pixels:
            return False
        left_pixels.append(left)
        right_pixels.append(right)

    return True

def create_overhead_projection(frame_file: Path, corner_pixels_file: Path, field_file: Path, output_file: Path):

    if not isinstance(frame_file, Path):
        frame_file = Path(frame_file)

    if not isinstance(corner_pixels_file, Path):
        corner_pixels_file = Path(corner_pixels_file)

    if not isinstance(field_file, Path):
        field_file = Path(field_file)

    if not isinstance(output_file, Path):
        output_file = Path(output_file)

    if not output_file.parent.exists():
        output_file.parent.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(frame_file))
    ground, red_pixels, line_pixels = load_above.main(field_file)
    
    with open(corner_pixels_file, 'r') as file:
        pixels = json.loads(file.read())
    #ground = cv2.imread('above-black-and-red.png')

    #pixels = [(592, 229), (331, 173), (1013, 637), (981, 393), (420, 256)]

    #red_pixels = [(79, 236), (79, 269), (83, 99), (83, 104), (83, 162), (83, 212), (83, 236), (83, 269), (83, 294), (83, 343), (83, 401), (83, 406), (88, 99), (88, 406), (108, 212), (108, 294), (158, 162), (158, 220), (158, 221), (158, 284), (158, 285), (158, 343), (320, 99), (320, 211), (320, 212),
    #              (320, 294), (320, 406), (482, 162), (482, 220), (482, 221), (482, 284), (482, 285), (482, 343), (532, 212), (532, 294), (552, 99), (552, 406), (557, 99), (557, 104), (557, 162), (557, 212), (557, 236), (557, 269), (557, 294), (557, 343), (557, 401), (557, 406), (561, 236), (561, 269)]


    #red_pixels = [(482, 343), 
    #              (532, 212), (532, 294), 
    #              (557, 162), (557, 212)]

    #red_pixels = [(482, 343), (532, 212), (532, 294), (557, 162), (557, 212)]


    pixel_pairs = list(itertools.product(pixels, red_pixels))

    best_match_count = 0
    best_match = None
    best_pairings = None
    best_matrix = None
    match_counts = {}

    for index, combination in enumerate(itertools.combinations(pixel_pairs, 4)):

        #if index < 7100 or index > 7450:
        #   continue

        image_copy = deepcopy(image)

        #if not use_pairing(combination):
        #   continue

        try:
            matrix = get_transition_matrix(4, combination)
            transition_matrix = np.linalg.inv(matrix)
        except np.linalg.LinAlgError as error:
            continue

        #pixel, red_pixel = combination[-1]

        #distance = (pixel[0] - new_red_x) ** 2 + (pixel[1] - new_red_y) ** 2
        #if distance > 250:
        #   continue

        pixels = [vector[0] for vector in combination]
        red_pixels = [vector[1] for vector in combination]

        skip = False
        for pixel, red_pixel in zip(pixels, red_pixels):
            new_red_pixel = np.matmul(transition_matrix, convert_vector(red_pixel))
            new_red_x = new_red_pixel[0] / new_red_pixel[2]
            new_red_y = new_red_pixel[1] / new_red_pixel[2]
            try:
                distance = (pixel[0] - new_red_x) ** 2 + (pixel[1] - new_red_y) ** 2
                if distance > 400:
                    skip=True
                    break
                new_red_x, new_red_y = int(new_red_x), int(new_red_y)
            except ValueError as error:
                skip=True
                break
            except OverflowError as error:
                skip=True
                break
            image_copy = cv2.circle(image_copy, (new_red_x, new_red_y), 5, (255,0,0), thickness=-1)

        if skip:
            continue
        
        matches = 0
        for x in range(ground.shape[1]):
            if skip:
                break
            for y in range(ground.shape[0]):
                if skip:
                    break
                pixel = ground[y, x, :]
                if load_above.is_dark_pixel(pixel):
                    continue
                new_point = np.matmul(transition_matrix, np.array([x, y, 1]))
                x_, y_ = new_point[0] / new_point[2], new_point[1] / new_point[2]
                try:
                    x_, y_ = int(x_), int(y_)
                except ValueError as error:
                    skip = True
                    break

                if 0 <= x_ and x_ < image_copy.shape[1] and 0 <= y_ and y_ < image_copy.shape[0] and is_white_pixel(image_copy[y_,x_,:], threshold=175):
                    matches += 1
                    image_copy = cv2.circle(image_copy, (x_,y_), 3, (0,0,255), -1)
                    #image_copy[y_, x_, :] = (0,0,255)

        if skip:
            continue
        if matches >= best_match_count:
            best_match_count = matches
            best_match = image_copy
            best_pairings = combination
            best_matrix = matrix
            cv2.imwrite(f'output_0_x/{index}.jpg', image_copy)

        match_counts[index] = matches
    
    output_directory = output_file.parent
    with open('matches.json', 'w+') as file:
        file.write(json.dumps(match_counts, indent=4))

    with open('pairings.json', 'w+') as file:
        file.write(json.dumps(best_pairings, indent=4))

    broadcast = cv2.imread('broadcast_img_0.png')

    for x in range(broadcast.shape[1]):
        for y in range(broadcast.shape[0]):
            if load_above.is_black_pixel(broadcast[y,x,:], threshold=0):
                new_point = np.matmul(best_matrix, np.array([x,y,1]))
                new_x, new_y = new_point[0] / new_point[2], new_point[1] / new_point[2]
                new_x, new_y = int(new_x), int(new_y)
                ground = cv2.circle(ground, (new_x, new_y), 1, (0,0,255), -1)

    cv2.imwrite(output_file, ground)

if __name__ == '__main__':

    warnings.filterwarnings("ignore")

    frame_file = Path(sys.agrv[1])
    corner_pixels_file = Path(sys.argv[2])
    field_file = Path(sys.argv[3])
    output_file = Path(sys.argv[4])

