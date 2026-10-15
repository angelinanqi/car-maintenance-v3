'use client'

import { ChakraProvider, defaultSystem } from '@chakra-ui/react'

import { SessionProvider } from "../SessionProvider";
import { Toaster } from "./toaster";

export function Provider(props) {
  return (
    <ChakraProvider value={defaultSystem}>
      <SessionProvider>{props.children}<Toaster /></SessionProvider>
    </ChakraProvider>
  )
}
