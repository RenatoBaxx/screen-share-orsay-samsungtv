import CoreAudio
import CoreGraphics
import CoreMedia
import Foundation
import ScreenCaptureKit

private func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data(("System audio capture: " + message + "\n").utf8))
    exit(1)
}

private final class AudioOutput: NSObject, SCStreamOutput, SCStreamDelegate {
    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
                of outputType: SCStreamOutputType) {
        guard outputType == .audio, sampleBuffer.isValid else { return }
        guard let description = sampleBuffer.formatDescription,
              let format = CMAudioFormatDescriptionGetStreamBasicDescription(description) else {
            fail("missing audio format")
        }
        let audio = format.pointee
        guard audio.mFormatID == kAudioFormatLinearPCM,
              audio.mFormatFlags & kAudioFormatFlagIsFloat != 0,
              audio.mFormatFlags & kAudioFormatFlagIsBigEndian == 0,
              audio.mBitsPerChannel == 32, audio.mSampleRate == 48_000,
              audio.mChannelsPerFrame == 2 else {
            fail("expected 48 kHz stereo float PCM from ScreenCaptureKit")
        }
        let frames = sampleBuffer.numSamples
        guard frames > 0 else { return }
        do {
            try sampleBuffer.withAudioBufferList { list, _ in
                let buffers = UnsafeMutableAudioBufferListPointer(list.unsafeMutablePointer)
                if buffers.count == 1 {
                    guard buffers[0].mNumberChannels == 2,
                          let data = buffers[0].mData,
                          buffers[0].mDataByteSize >= frames * 2 * MemoryLayout<Float>.size else {
                        fail("invalid interleaved audio buffer")
                    }
                    try FileHandle.standardOutput.write(contentsOf:
                        Data(bytes: data, count: frames * 2 * MemoryLayout<Float>.size))
                } else if buffers.count == 2 {
                    guard buffers[0].mNumberChannels == 1,
                          buffers[1].mNumberChannels == 1,
                          let leftData = buffers[0].mData, let rightData = buffers[1].mData,
                          buffers[0].mDataByteSize >= frames * MemoryLayout<Float>.size,
                          buffers[1].mDataByteSize >= frames * MemoryLayout<Float>.size else {
                        fail("invalid planar audio buffers")
                    }
                    let left = leftData.assumingMemoryBound(to: Float.self)
                    let right = rightData.assumingMemoryBound(to: Float.self)
                    var samples = [Float](repeating: 0, count: frames * 2)
                    for frame in 0..<frames {
                        samples[frame * 2] = left[frame]
                        samples[frame * 2 + 1] = right[frame]
                    }
                    try samples.withUnsafeBytes {
                        try FileHandle.standardOutput.write(contentsOf: Data($0))
                    }
                } else {
                    fail("unsupported audio buffer layout")
                }
            }
        } catch {
            fail("cannot write audio: \(error)")
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fail("stream stopped: \(error)")
    }
}

@main
struct CaptureSystemAudio {
    static func main() async {
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false, onScreenWindowsOnly: true)
            guard let display = content.displays.first(where: { $0.displayID == CGMainDisplayID() })
                    ?? content.displays.first else {
                fail("no display available for system audio capture")
            }
            let filter = SCContentFilter(display: display,
                                         excludingApplications: [], exceptingWindows: [])
            let configuration = SCStreamConfiguration()
            configuration.width = 32
            configuration.height = 32
            configuration.capturesAudio = true
            configuration.excludesCurrentProcessAudio = false
            configuration.sampleRate = 48_000
            configuration.channelCount = 2
            let output = AudioOutput()
            let stream = SCStream(filter: filter, configuration: configuration, delegate: output)
            try stream.addStreamOutput(output, type: .audio,
                                       sampleHandlerQueue: DispatchQueue(label: "orsay.system-audio"))
            try await stream.startCapture()
            FileHandle.standardError.write(Data("System audio capture ready\n".utf8))
            while let line = readLine() {
                if line == "q" { break }
            }
            try await stream.stopCapture()
        } catch {
            fail("\(error)")
        }
    }
}
