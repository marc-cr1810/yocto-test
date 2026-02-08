cmake_minimum_required(VERSION 3.10)
project(talon VERSION 1.0)

add_executable(talon main.cpp)

install(TARGETS talon DESTINATION bin)
