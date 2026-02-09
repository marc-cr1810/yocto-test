cmake_minimum_required(VERSION 3.10)
project(legs-main VERSION 1.0)

add_executable(legs-main main.cpp)

install(TARGETS legs-main DESTINATION bin)
