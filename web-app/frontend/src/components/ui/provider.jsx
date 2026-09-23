'use client'

import { ChakraProvider, defaultSystem } from '@chakra-ui/react'

import { PrototypeProvider } from "../PrototypeProvider";
import { Toaster } from "./toaster";

export function Provider(props) {
  return (
    <ChakraProvider value={defaultSystem}>
      <PrototypeProvider>{props.children}<Toaster /></PrototypeProvider>
    </ChakraProvider>
  )
}
