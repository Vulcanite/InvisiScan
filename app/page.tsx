"use client"

import type React from "react"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Upload, X, CheckCircle, AlertCircle, Info, Download, Paperclip, Eye, Shield } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import mammoth from "mammoth"

interface ProcessingData {
  original_filename?: string;
  image_size?: {
    width: number;
    height: number;
  };
  file_size?: number;
  format?: string;
  mode?: string;
  processing_status: string;
  input_type: 'image' | 'text';
}

interface ApiResponse {
  message: string;
  data: ProcessingData;
  processed_image?: {
    base64: string;
    content_type: string;
  };
  redacted_text?: string;
  analysis_summary?:string
}

type InputType = 'image' | 'text';

export default function DataScanPage() {
  const [inputData, setInputData] = useState<File | string | null>(null)
  const [inputType, setInputType] = useState<InputType | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<"idle" | "success" | "error">("idle")
  const [preview, setPreview] = useState<string | null>(null)
  const [processedData, setProcessedData] = useState<ProcessingData | null>(null)
  const [processedImage, setProcessedImage] = useState<string | null>(null)
  const [redactedText, setRedactedText] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [inputFormat, setInputFormat] = useState<File | string | null>(null)

  const isImageFile = (file: File) => {
    return file.type.startsWith('image/')
  }

  const isAllowedFile = (file: File) => {
  const allowedWordTypes = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // .docx
    "application/msword", // .doc
  ]
    return file.type.startsWith("image/") || allowedWordTypes.includes(file.type)
  }
  const isWordFile = (file: File) => {
    return file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" || file.type === "application/msword"
  }
  const isTextFile = (file: File) => {
    return file.type.startsWith("text/") || file.name.toLowerCase().endsWith(".txt")
  }
  
  const resetState = () => {
    setUploadStatus("idle")
    setProcessedData(null)
    setProcessedImage(null)
    setMessage(null)
    setRedactedText(null)
    setPreview(null)
  }

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if(!file) return
    if (isImageFile(file)) {
      setInputData(file)
      setInputType('image')
      resetState()

      // Create image preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreview(e.target?.result as string)
      }
      reader.readAsDataURL(file)

      // Clear textarea
      if (textareaRef.current) {
        textareaRef.current.value = ""
      }
    } else if (isWordFile(file)) {
        setInputType("text") // treat as "text" input type
        resetState()
        const arrayBuffer = await file.arrayBuffer()
        const { value } = await mammoth.extractRawText({ arrayBuffer })
        setInputData(value.trim())
        setPreview(value.trim())
        setInputFormat(file)
        //setPreview(null)

        if (textareaRef.current) textareaRef.current.value = ""
    } else if (isTextFile(file)) {
        setInputType("text") // treat as "text" input type
        resetState()
        const reader = new FileReader()
        reader.onload = (event) => {
          const textContent = (event.target?.result as string)?.trim()
          if (textContent) {
            setInputData(textContent) 
            setPreview(textContent) 
            setInputFormat(file)
          }
        }
        reader.readAsText(file)
    }
      else {
        alert("Please select an image or Word document")
        event.target.value = ""
  }
  }

  const handleTextChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = event.target.value
    
    if (text.trim()) {
      setInputData(text)
      setInputType('text')
      resetState()
      setPreview(null)
      
      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    } else {
      setInputData(null)
      setInputType(null)
      resetState()
    }
  }

  const handlePaste = async (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = event.clipboardData?.items
    
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        
        // Check if pasted item is an image
        if (item.type.startsWith('image/')) {
          event.preventDefault()
          const file = item.getAsFile()
          
          if (file) {
            setInputData(file)
            setInputType('image')
            resetState()

            // Create image preview
            const reader = new FileReader()
            reader.onload = (e) => {
              setPreview(e.target?.result as string)
            }
            reader.readAsDataURL(file)

            // Clear textarea
            if (textareaRef.current) {
              textareaRef.current.value = ""
            }
          }
          return
        }
      }
    }
    
    // If no image was pasted, handle as text (default behavior)
    // The text will be handled by handleTextChange
  }

  const handleScan = async () => {
    if (!inputData || !inputType) return

    setUploading(true)
    setUploadStatus("idle")

    try {
      const formData = new FormData()
      
      if (inputType === 'image' && inputData instanceof File) {
        formData.append("image", inputData)
      } else if (inputType === 'text' && typeof inputData === 'string') {
        formData.append("text_input", inputData.trim())
      // } else if (inputType === "text" && inputData instanceof File) {
      //     // Word document upload
      //     formData.append("document", inputData)
      // }

      const response = await fetch("http://localhost:8000/api/scan", {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        const result: ApiResponse = await response.json()
        setUploadStatus("success")
        setProcessedData(result.data)
        
        if (result.processed_image) {
          setProcessedImage(`data:${result.processed_image.content_type};base64,${result.processed_image.base64}`)
        }
        
        if (result.redacted_text) {
          setRedactedText(result.redacted_text)
        }

        if (result.message) {
          setMessage(result.message)
        }

      } else {
        setUploadStatus("error")
      }
    }} catch (error) {
      console.error("Scan failed:", error)
      setUploadStatus("error")
    } finally {
      setUploading(false)
    }
  }

  const handleDownload = () => {
    if (inputType === 'image' && processedImage && processedData) {
      // Download processed image
      const link = document.createElement('a')
      link.href = processedImage
      
      const originalName = processedData.original_filename || 'image'
      const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.')) || originalName
      const extension = processedData.format?.toLowerCase() || 'jpg'
      const downloadFilename = `${nameWithoutExt}_processed.${extension}`
      
      link.download = downloadFilename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } else if (inputType === 'text' && redactedText) {
      // Download redacted text
      const blob = new Blob([redactedText], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'redacted_text.txt'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  }

  const clearAll = () => {
    setInputData(null)
    setInputType(null)
    setPreview(null)
    setUploadStatus("idle")
    setProcessedData(null)
    setProcessedImage(null)
    setRedactedText(null)
    setMessage(null)

    if (textareaRef.current) {
      textareaRef.current.value = ""
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const getButtonText = () => {
    if (uploading) {
      return inputType === 'image' ? "Analyzing..." : "Scanning..."
    }
    return inputType === 'image' ? "Identify Visual Cues" : "Scan for Sensitive Data"
  }

  const getButtonIcon = () => {
    return inputType === 'image' ? <Eye className="h-4 w-4 mr-2" /> : <Shield className="h-4 w-4 mr-2" />
  }

  const hasInput = inputData !== null

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto mt-8">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-foreground">Privacy First!</h1>
        </div>
        
        <div className={`grid gap-6 ${processedData || processedImage || redactedText ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 place-items-center"}`}>
          {/* Input Card */}
          <motion.div
            layout  // enables smooth reposition when layout changes
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className={`${processedData || processedImage || redactedText ? "" : "max-w-md w-full"}`}
          >
          <Card className={`${processedData || processedImage || redactedText ? "" : "max-w-md w-full"}`}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Smart Input
              </CardTitle>
              <CardDescription>Type text, paste an image, or attach a file to analyze for sensitive information or visual clues</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Unified Input Area */}
              <div className="space-y-3">
                {/* File Input (Hidden) */}
                <input 
                  ref={fileInputRef}
                  type="file" 
                  accept="image/*,.doc,.docx,.txt"
                  onChange={handleFileSelect} 
                  className="hidden" 
                  id="file-input" 
                />
                
                {/* Text Input with File Attachment */}
                <div className="relative">
                  <textarea
                    ref={textareaRef}
                    onChange={handleTextChange}
                    onPaste={handlePaste}
                    placeholder="Type or paste your text here, or paste an image (Ctrl+V)..."
                    className="w-full h-40 p-3 pr-12 border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute bottom-2 right-2 h-8 w-8 p-0"
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach image file"
                  >
                    <Paperclip className="h-4 w-4" />
                  </Button>
                </div>
                
                <p className="text-xs text-muted-foreground">
                  💡 Tip: You can paste images directly (Ctrl+V), type text, or click the paperclip to attach an image file
                </p>
              </div>

              {/* Image Preview */}
              {preview && inputType === 'image' && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.3 }}
                    className="relative"
                  >
                    <img
                      src={preview}
                      alt="Preview"
                      className="w-full h-48 object-cover rounded-lg border"
                    />
                    <Button variant="destructive" size="sm" className="absolute top-2 right-2" onClick={clearAll}>
                      <X className="h-4 w-4" />
                    </Button>
                  </motion.div>
              )}

              {/* Text Document Preview */}
              {inputType === 'text' && inputFormat instanceof File && (
                <div className="flex items-center justify-between">
                  <p className="text-sm">📄 {inputFormat.name}</p>
                  <Button 
                    onClick={handleDownload} 
                    variant="outline" 
                    size="sm"
                    className="flex items-center gap-2"
                  >
                    <Download className="h-4 w-4" />
                    Download
                  </Button>
                </div>
              )}

              {/* Input Info */}
              {/* {hasInput && (
                <div className="text-sm text-muted-foreground space-y-1">
                  {inputType === 'image' && inputData instanceof File && (
                    <>
                      <p><span className="font-medium">File:</span> {inputData.name}</p>
                      <p><span className="font-medium">Size:</span> {(inputData.size / 1024).toFixed(2)} KB</p>
                    </>
                  )}
                  {inputType === 'text' && typeof inputData === 'string' && (
                    <p><span className="font-medium">Text Length:</span> {inputData.length} characters</p>
                  )}
                  <p><span className="font-medium">Input Type:</span> {inputType === 'image' ? 'Image' : 'Text'}</p>
                </div>
              )} */}

              {/* Action Buttons */}
              <div className="flex gap-2">
                <Button onClick={handleScan} disabled={!hasInput || uploading} className="flex-1">
                  {getButtonIcon()}
                  {getButtonText()}
                </Button>
                
                {hasInput && (
                  <Button variant="outline" onClick={clearAll}>
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {/* Status Messages */}
              {uploadStatus === "success" && (
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm">Analysis completed successfully!</span>
                </div>
              )}

              {uploadStatus === "error" && (
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">Analysis failed. Please try again.</span>
                </div>
              )}
            </CardContent>
          </Card>
          </motion.div>
          {/* Results Card */}
          <AnimatePresence>
          {(processedData || processedImage || redactedText) && (
            <motion.div
              layout
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 50 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="h-5 w-5" />
                  Analysis Results
                </CardTitle>
                <CardDescription>
                  {message}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Processed Image */}
                {processedImage && inputType === 'image' && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium">Processed Image:</h3>
                      <Button 
                        onClick={handleDownload} 
                        variant="outline" 
                        size="sm"
                        className="flex items-center gap-2"
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </Button>
                    </div>
                    <img
                      src={processedImage}
                      alt="Processed"
                      className="w-full h-48 object-cover rounded-lg border"
                    />
                  </div>
                )}

                {/* Redacted Text */}
                {redactedText && inputType === 'text' && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium">Redacted Text:</h3>
                      <Button 
                        onClick={handleDownload} 
                        variant="outline" 
                        size="sm"
                        className="flex items-center gap-2"
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </Button>
                    </div>
                    <div className="bg-muted p-3 rounded-lg max-h-64 overflow-auto">
                      <pre className="whitespace-pre-wrap font-mono text-sm">{redactedText}</pre>
                    </div>
                  </div>
                )}

                {/* Processing Data */}
                {processedData && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Analysis Information:</h3>
                    <div className="bg-muted p-3 rounded-lg text-sm space-y-1">
                      {processedData.original_filename && (
                        <p><span className="font-medium">Filename:</span> {processedData.original_filename}</p>
                      )}
                      {processedData.image_size && (
                        <p><span className="font-medium">Dimensions:</span> {processedData.image_size.width} × {processedData.image_size.height}</p>
                      )}
                      {processedData.file_size && (
                        <p><span className="font-medium">File Size:</span> {(processedData.file_size / 1024).toFixed(2)} KB</p>
                      )}
                      {processedData.format && (
                        <p><span className="font-medium">Format:</span> {processedData.format}</p>
                      )}
                      {processedData.mode && (
                        <p><span className="font-medium">Color Mode:</span> {processedData.mode}</p>
                      )}
                      <p><span className="font-medium">Input Type:</span> {processedData.input_type}</p>
                      <p><span className="font-medium">Status:</span> <span className="text-green-600 capitalize">{processedData.processing_status}</span></p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            </motion.div>
          )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}